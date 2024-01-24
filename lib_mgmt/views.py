from .models import Reader, Book, Category, BorrowRecord, Inventory, OperationLog
from .utils import upload_validator
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import View
from django.views.decorators.http import require_POST
from django.core.exceptions import ObjectDoesNotExist
from django import forms
from django.forms.models import model_to_dict
from django.db.models import Q, Count
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.shortcuts import get_object_or_404, render, redirect
from datetime import datetime, timedelta

# 分页逻辑封装
def paginate(request, Obj, page=10):
    page = request.POST.get('page', 1)
    count = Obj.count()
    page_count = int((Obj.count()-1)/10) + 1
    Obj = Obj[(int(page)-1)*10:int(page)*10]
    return Obj, count, page_count

# 检查用户是否为管理员的函数
def is_admin(user):
    return user.is_authenticated and user.is_staff

def admin_only(view_func): # 如果不是管理员，重定向到用户中心
    decorated_view_func = user_passes_test(is_admin, login_url='/user/')(view_func)
    return decorated_view_func

# 首页视图
def index(request):
    return render(request, 'index.html')

# ----[API]----

# 用户借阅统计，for chart.js
class UserBorrowStatsView(View):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            days = int(request.GET.get('days', 7))  # 默认为7天
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days-1)

            stats = []
            for i in range(days):
                date = start_date + timedelta(days=i)
                count = BorrowRecord.objects.filter(reader=request.user.reader, borrow_date=date).count()
                stats.append({'date': date, 'count': count})

            return JsonResponse(stats, safe=False)
        else:
            return JsonResponse({'success': False, 'error': 'Permission denied'})

class TopBorrowedBooksView(View):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            #筛选近一个月的记录
            top_books = BorrowRecord.objects.filter(borrow_date__gte=datetime.now() - timedelta(days=30)) \
                                            .values('inventory__book__title') \
                                            .annotate(count=Count('inventory__book')) \
                                            .order_by('-count')[:5]
            return JsonResponse(list(top_books), safe=False)
        else:
            return JsonResponse({'success': False, 'error': 'Permission denied'})

class CategoryView(View):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            categories = Category.objects.values('category_number', 'name')
            return JsonResponse(list(categories), safe=False)
        else:
            return JsonResponse({'success': False, 'error': 'Permission denied'})

class BookView(View):
    # 可以通过输入搜索书名的关键字检索图书
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            keyword = request.GET.get('keyword', '')
            books = Book.objects.filter(title__contains=keyword)
            book_list = []
            for book in books:
                book_dict = model_to_dict(book)
                book_dict['category_name'] = book.category.name
                book_dict['inventory_count'] = Inventory.objects.filter(book=book).count()
                book_list.append(book_dict)
            return JsonResponse(book_list, safe=False)
        else:
            return JsonResponse({'success': False, 'error': 'Permission denied'})   
# ----[用户视图]----

# 注册表格
class RegisterUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user

# 信息编辑表格
class RegisterUserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

# 管理员注册用户表格
# 需要同时修改Reader和User两个模型
class ControlUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    is_staff = forms.BooleanField(required=False)
    max_borrow_limit = forms.IntegerField(required=True, initial=5)
    password2 = None

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "is_staff", "max_borrow_limit")
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.is_staff = self.cleaned_data["is_staff"]

        if commit:
            user.save()
            readerRecord = Reader(user=User.objects.get(username=user.username), max_borrow_limit=self.cleaned_data["max_borrow_limit"])
            readerRecord.save()
        return user

# 管理员编辑用户表格
# 需要同时修改Reader和User两个模型
class ControlUserEditForm(UserChangeForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    is_staff = forms.BooleanField(required=False)
    max_borrow_limit = forms.IntegerField(required=True, initial=5)
    password1 = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "is_staff", "max_borrow_limit")
    # 读取当前instance的值
    def __init__(self, *args, **kwargs):
        super(ControlUserEditForm, self).__init__(*args, **kwargs)
        self.fields['username'].initial = self.instance.username
        self.fields['first_name'].initial = self.instance.first_name
        self.fields['last_name'].initial = self.instance.last_name
        self.fields['email'].initial = self.instance.email
        self.fields['is_staff'].initial = self.instance.is_staff
        self.fields['max_borrow_limit'].initial = self.instance.reader.max_borrow_limit
        self.fields['password1'].required = False

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = self.cleaned_data["is_staff"]
        # 无密码则不修改
        if self.cleaned_data["password1"] != '':
            user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()
            readerRecord = Reader.objects.get(user=User.objects.get(username=user.username))
            readerRecord.max_borrow_limit = self.cleaned_data["max_borrow_limit"]
            readerRecord.save()
        return user
    
# 用户注册视图
def user_register(request):
    if request.method == 'POST':
        form = RegisterUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            readerRecord = Reader(user=User.objects.get(username=form.cleaned_data['username']), max_borrow_limit=5)
            readerRecord.save()
            return redirect('lib:user_login')
    else:
        form = RegisterUserCreationForm()
    return render(request, 'auth/register.html', {'form': form})

# 用户登录视图
def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = User.objects.get(username=username)
        # 多层特判
        if user is None:
            return render(request, 'auth/login.html', {'error': 'Invalid username or password!'})
        if not user.is_active:
            return render(request, 'auth/login.html', {'error': 'Your account is disabled!'})
        user = authenticate(username=username, password=password)
        if user is None:
            return render(request, 'auth/login.html', {'error': 'Invalid username or password!'})
        login(request, user)
        return redirect('lib:user_center')
    else:
        return render(request, 'auth/login.html')

# 用户登出视图
@login_required(login_url='')
def user_logout(request):
    logout(request)
    return redirect('lib:index')  # 登出后重定向到首页

# 用户中心视图
@login_required(login_url='')  # 未登录用户将重定向到首页（假设首页的 URL 是 '/'）
def user_center(request):
    number = dict()
    number['borrowed'] = BorrowRecord.objects.filter(reader=request.user.reader, status=1).count()
    # 七天之后将过期的，过期的不算
    number['soon_overdue'] = BorrowRecord.objects.filter(reader=request.user.reader, status=1, return_date__lte=datetime.now() + timedelta(days=7), return_date__gt=datetime.now()).count()
    number['overdue'] = BorrowRecord.objects.filter(reader=request.user.reader, status=1, return_date__lte=datetime.now()).count()
    number['remaining_quota'] = request.user.reader.max_borrow_limit - number['borrowed']
    return render(request, 'user/user_center.html', {'user': request.user, 'number': number})

# 借阅记录查询视图
@login_required(login_url='')
def user_borrow_records(request):
    records = BorrowRecord.objects.filter(reader=request.user.reader, status=1)
    count = records.count()
    maxBorrow = request.user.reader.max_borrow_limit
    remaining = maxBorrow - count
    return render(request, 'user/borrow_records.html', {'records': records, 'count': count, 'remaining': remaining})

# 借阅图书检索视图
# 检索后点击对应图书，返回该图书的 book_id
@login_required(login_url='')
def user_borrow_search(request):
    books = Book.objects.none()  # 初始化一个空的 QuerySets
    if request.method == 'POST':
        if 'books_keyword' in request.POST:
            keyword = request.POST['books_keyword']
            # 拆解关键字，按空格分开，分别匹配
            keywords = keyword.split(' ')
            # 任意字段匹配搜索
            for keyword in keywords:
                categories = Category.objects.filter(name__contains=keyword)
                books = books | Book.objects.filter(
                    Q(title__contains=keyword) |
                    Q(author__contains=keyword) |
                    Q(publisher__contains=keyword) |
                    Q(publish_date__contains=keyword) |
                    Q(index_number__contains=keyword) |
                    Q(category__in=categories)
                )
            books, count, page_count = paginate(request, books)
            # 添加分类号解析成名字的字段
            # 添加库存记录数字段
            book_list = []
            for book in books:
                book_dict = model_to_dict(book)
                book_dict['category_name'] = book.category.name
                book_dict['inventory_count'] = Inventory.objects.filter(book=book).count()
                book_list.append(book_dict)

            return JsonResponse({'success': True, 'keyword': keywords, 'books': book_list, 'page_count': page_count, 'count': count}, status=200)      
    else:
        return render(request, 'user/borrow_search.html')

# 某图书库存查看视图，返回图书信息+库存记录
@login_required(login_url='')
def user_borrow_inv(request):
    book = Book.objects.get(id=request.GET['book_id'])
    # 按照status排序，status=1的排在前面
    inv_records = Inventory.objects.filter(book=book).order_by('status').values('id', 'book__title', 'location', 'status')
    inv_list = list(inv_records)
    # 找到该inv的借阅记录的最新应归还时间，不用first，status=1的只有一条
    for inv in inv_list:
        if inv['status'] == 2:
            inv['return_date'] = BorrowRecord.objects.filter(inventory=inv['id'], status=1).first().return_date.strftime('%Y-%m-%d')
        else:
            inv['return_date'] = '-'
        inv['get_status_display'] = Inventory.objects.get(id=inv['id']).get_status_display()
    return render(request, 'user/shard_borrow_inv.html', {'book': book, 'inventory': inv_list})

# 借阅图书
@login_required(login_url='')
@require_POST
def user_borrow_book(request):
    inventory_id = request.POST['inv_id']
    inv = Inventory.objects.get(id=inventory_id, status=1)
    maxBorrow = request.user.reader.max_borrow_limit
    quota = maxBorrow - BorrowRecord.objects.filter(reader=request.user.reader, status=1).count()
    if quota <= 0:
        return JsonResponse({'success': False, 'error': "借阅失败，剩余借阅配额不足！"}, status=200)
    if (inv is not None):
        inv.status = 2
        inv.last_borrowed_on = datetime.now()
        inv.last_borrowed_by = request.user.reader
        inv.save()
        new_record = BorrowRecord(reader=request.user.reader, inventory=inv, borrow_date=datetime.now(), return_date=datetime.now() + timedelta(days=30), status=1)
        new_record.save()
        return JsonResponse({'success': True}, status=200)
    return JsonResponse({'success': False}, status=400)


# 归还图书
@login_required(login_url='')
@require_POST
def user_return_book(request):
    record_id = request.POST['record_id']
    record = BorrowRecord.objects.get(id=record_id, status=1, reader=request.user.reader)
    if record is not None:
        record.status = 0
        record.save()
        inv = record.inventory
        inv.status = 1
        inv.save()
        return JsonResponse({'success': True}, status=200)
    return JsonResponse({'success': False}, status=400)

# 查看个人信息视图
@login_required(login_url='')
def user_view_profile(request):
    return render(request, 'user/view_profile.html', {'user': request.user})

# 修改个人信息视图
@login_required(login_url='')
def user_edit_profile(request):
    if request.method == 'POST':
        form = RegisterUserEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('lib:user_view_profile')
    else:
        form = RegisterUserEditForm(instance=request.user)
    return render(request, 'user/edit_profile.html', {'form': form})

# 修改密码视图
@login_required(login_url='')
def user_change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(data=request.POST, user=request.user)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            # 取消登录态，需要重新登录
            logout(request)
            return redirect('lib:user_view_profile')
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, 'user/change_password.html', {'form': form})

# ----[管理员视图]----

# 管理中心视图
@admin_only
def admin_center(request):
    return render(request, 'admin/admin_center.html')

# 读者信息视图
@admin_only
def reader_list(request):
    # 搜索功能
    if request.method == 'POST':
        keyword = request.POST['readers_keyword']
        # 拆解关键字，按空格分开，分别匹配
        keywords = keyword.split(' ')
        # 任意字段匹配搜索
        readers = Reader.objects.none()
        for keyword in keywords:
            readers = readers | Reader.objects.filter(
                Q(user__username__contains=keyword) |
                Q(user__first_name__contains=keyword) |
                Q(user__last_name__contains=keyword) |
                Q(user__email__contains=keyword)
            )
        readers, count, page_count = paginate(request, readers)
        # 添加分类号解析成名字的字段
        # 添加库存记录数字段
        reader_list = []
        for reader in readers:
            reader_dict = model_to_dict(reader)
            reader_dict['username'] = reader.user.username
            reader_dict['first_name'] = reader.user.first_name
            reader_dict['last_name'] = reader.user.last_name
            reader_dict['email'] = reader.user.email
            reader_dict['is_active'] = reader.user.is_active
            reader_dict['is_staff'] = reader.user.is_staff
            reader_dict['max_borrow_limit'] = reader.max_borrow_limit
            reader_list.append(reader_dict)
        return JsonResponse({'success': True, 'keyword': keywords, 'readers': reader_list, 'page_count': page_count, 'count': count}, status=200)
    else:
        return render(request, 'admin/reader_list.html')

@admin_only
def add_reader(request):
    # 使用其他部分和用户注册相同的表单，但是多添加“is_staff”和“max_borrow_limit”字段
    if request.method == 'POST':
        form = ControlUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': form.errors})
    else:
        form = ControlUserCreationForm()
        return render(request, 'admin/shard/reader/add.html', {'form': form})

@admin_only
def add_readers_bulk(request):
    if request.method == 'POST':
        csv_file = request.FILES['readers_file']
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({'success': False, 'error': 'File type error'})
        file_data = csv_file.read().decode("utf-8")
        valid, reason = upload_validator.reader_validate(file_data)
        if not valid:
            return JsonResponse({'success': False, 'error': reason})
        lines = file_data.split("\n")
        for line in lines:
            fields = line.split(",")
            user = User.objects.create_user(username=fields[0], first_name=fields[1], last_name=fields[2], email=fields[3], password=fields[4], is_staff=fields[5])
            readerRecord = Reader(user=user, max_borrow_limit=fields[6])
            readerRecord.save()
        return JsonResponse({'success': True})
    else:
        return render(request, 'admin/shard/reader/add_bulk.html')

@admin_only
def edit_reader(request):
    if request.method == 'POST':
        reader = Reader.objects.get(id=request.POST['reader_id'])
        form = ControlUserEditForm(request.POST, instance=reader.user)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': form.errors})
    else:
        reader = Reader.objects.get(id=request.GET['reader_id'])
        form = ControlUserEditForm(instance=reader.user)
        return render(request, 'admin/shard/reader/edit.html', {'form': form, 'reader': reader})

@admin_only
def disable_reader(request):
    reader = Reader.objects.get(id=request.POST['reader_id'])
    user = reader.user
    if user.is_active:
        user.is_active = False
        user.save()
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False, 'error': 'User already disabled'})

@admin_only
def enable_reader(request):
    reader = Reader.objects.get(id=request.POST['reader_id'])
    user = reader.user
    if not user.is_active:
        user.is_active = True
        user.save()
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False, 'error': 'User already enabled'})
    
# 图书列表视图
@admin_only
def book_list(request):
    # 搜索功能
    if request.method == 'POST':
        keyword = request.POST['books_keyword']
        # 拆解关键字，按空格分开，分别匹配
        keywords = keyword.split(' ')
        # 任意字段匹配搜索
        books = Book.objects.none()
        for keyword in keywords:
            categories = Category.objects.filter(name__contains=keyword)
            books = books | Book.objects.filter(
                Q(title__contains=keyword) |
                Q(author__contains=keyword) |
                Q(publisher__contains=keyword) |
                Q(publish_date__contains=keyword) |
                Q(index_number__contains=keyword) |
                Q(category__in=categories)
            )
        books, count, page_count = paginate(request, books)
        # 添加分类号解析成名字的字段
        # 添加库存记录数字段
        book_list = []
        for book in books:
            book_dict = model_to_dict(book)
            book_dict['category_name'] = book.category.name
            book_dict['inventory_count'] = Inventory.objects.filter(book=book).count()
            book_list.append(book_dict)
        return JsonResponse({'success': True, 'keyword': keywords, 'books': book_list, 'page_count': page_count, 'count': count}, status=200)
    else:
        return render(request, 'admin/book_list.html')
            
# 图书增删改视图
@admin_only
def add_book(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        author = request.POST.get('author')
        publisher = request.POST.get('publisher')
        publish_date = request.POST.get('publish_date')
        index_number = request.POST.get('index_number')
        category = request.POST.get('category')
        description = request.POST.get('description')

        category = Category.objects.get_or_create(category_number=category, defaults={'name': '未命名分类'})[0]
        try:
            Book.objects.create(title=title, author=author, publisher=publisher, publish_date=publish_date, index_number=index_number, category=category, description=description)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
        return JsonResponse({'success': True})
    else:
        return render(request, 'admin/shard/book/add.html')

@admin_only
def add_books_bulk(request):
    if request.method == 'POST':
        csv_file = request.FILES['books_file']
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({'success': False, 'error': 'File type error'})
        file_data = csv_file.read().decode("utf-8")
        valid, reason = upload_validator.book_validate(file_data)
        if not valid:
            return JsonResponse({'success': False, 'error': reason})
        lines = file_data.split("\n")
        for line in lines:
            fields = line.split(",")
            catagory= Category.objects.get_or_create(category_number=fields[5], defaults={'name': '未命名分类'})[0]
            try:
                Book.objects.create(title=fields[0], author=fields[1], publisher=fields[2], publish_date=fields[3], 
                                    index_number=fields[4], category=catagory, description=fields[6])
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        return JsonResponse({'success': True})
    else:
        return render(request, 'admin/shard/book/add_bulk.html')

@admin_only
def edit_book(request):
    if request.method == 'POST':
        try:
            book = Book.objects.get(id=request.POST['book_id'])
            book.title = request.POST['title']
            book.author = request.POST['author']
            book.publisher = request.POST['publisher']
            book.publish_date = request.POST['publish_date']
            book.index_number = request.POST['index_number']
            book.category = Category.objects.get_or_create(category_number=request.POST['category'], defaults={'name': '未命名分类'})[0]
            book.description = request.POST['description']
            book.save()
            return JsonResponse({'success': True})
        except ObjectDoesNotExist:
            return JsonResponse({'success': False, 'error': 'Book not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    else:
        try:
            book = Book.objects.get(id=request.GET['book_id'])
            return render(request, 'admin/shard/book/edit.html', {'book': book})
        except ObjectDoesNotExist:
            return JsonResponse({'success': False, 'error': 'Book not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

@admin_only
@require_POST
def delete_book(request):
    try:
        book = Book.objects.get(id=request.POST['book_id'])
        # 删除图书前需要检查是否有库存记录
        if Inventory.objects.filter(book=book).count() > 0:
            return JsonResponse({'success': False, 'error': 'There are inventories for this book'})
        book.delete()
        return JsonResponse({'success': True})
    except ObjectDoesNotExist:
        return JsonResponse({'success': False, 'error': 'Book not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# 分类列表视图
@admin_only
def category_list(request):
    # 搜索功能
    if request.method == 'POST':
        keyword = request.POST['categories_keyword']
        # 拆解关键字，按空格分开，分别匹配
        keywords = keyword.split(' ')
        # 任意字段匹配搜索
        categories = Category.objects.none()
        for keyword in keywords:
            categories = categories | Category.objects.filter(
                Q(category_number__contains=keyword) |
                Q(name__contains=keyword)
            )
        categories, count, page_count = paginate(request, categories)
        return JsonResponse({'success': True, 'keyword': keywords, 'categories': list(categories.values()), 'page_count': page_count, 'count': count}, status=200)
    else:
        return render(request, 'admin/category_list.html')

@admin_only
def add_category(request):
    if request.method == 'POST':
        category_number = request.POST['category_number']
        name = request.POST['name']
        try:
            Category.objects.create(category_number=category_number, name=name)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
        return JsonResponse({'success': True})
    else:
        return render(request, 'admin/shard/category/add.html')
    
@admin_only
def add_categories_bulk(request):
    if request.method == 'POST':
        csv_file = request.FILES['categories_file']
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({'success': False, 'error': 'File type error'})
        file_data = csv_file.read().decode("utf-8")
        valid, reason = upload_validator.category_validate(file_data)
        if not valid:
            return JsonResponse({'success': False, 'error': reason})
        lines = file_data.split("\n")
        for line in lines:
            fields = line.split(",")
            try:
                Category.objects.create(category_number=fields[0], name=fields[1])
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        return JsonResponse({'success': True})
    else:
        return render(request, 'admin/shard/category/add_bulk.html')

@admin_only
def edit_category(request):
    if request.method == 'POST':
        try:
            category = Category.objects.get(id=request.POST['category_id'])
            category.category_number = request.POST['category_number']
            category.name = request.POST['name']
            category.save()
            return JsonResponse({'success': True})
        except ObjectDoesNotExist:
            return JsonResponse({'success': False, 'error': 'Category not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    else:
        try:
            category = Category.objects.get(id=request.GET['category_id'])
            return render(request, 'admin/shard/category/edit.html', {'category': category})
        except ObjectDoesNotExist:
            return JsonResponse({'success': False, 'error': 'Category not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

@admin_only
def delete_category(request):
    try:
        category = Category.objects.get(id=request.POST['category_id'])
        # 删除分类前需要检查是否有图书使用该分类
        if Book.objects.filter(category=category).count() > 0:
            return JsonResponse({'success': False, 'error': 'There are books using this category'})
        category.delete()
        return JsonResponse({'success': True})
    except ObjectDoesNotExist:
        return JsonResponse({'success': False, 'error': 'Category not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# 库存记录视图
@admin_only
def inventory_list(request):
    # 搜索功能
    if request.method == 'POST':
        keyword = request.POST['inventories_keyword']
        # 拆解关键字，按空格分开，分别匹配
        keywords = keyword.split(' ')
        # 任意字段匹配搜索
        inventories = Inventory.objects.none()
        for keyword in keywords:
            inventories = inventories | Inventory.objects.filter(
                Q(book__title__contains=keyword) |
                Q(book__author__contains=keyword) |
                Q(book__publisher__contains=keyword) |
                Q(book__publish_date__contains=keyword) |
                Q(book__index_number__contains=keyword) |
                Q(book__category__category_number__contains=keyword) |
                Q(book__category__name__contains=keyword) |
                Q(status__contains=keyword) |
                Q(location__contains=keyword)
            )
        inventories, count, page_count = paginate(request, inventories)
        # 添加分类号解析成名字的字段
        # 添加库存记录数字段
        inventory_list = []
        for inventory in inventories:
            inventory_dict = model_to_dict(inventory)
            inventory_dict['book_title'] = inventory.book.title
            inventory_dict['book_author'] = inventory.book.author
            inventory_dict['book_publisher'] = inventory.book.publisher
            inventory_dict['book_publish_date'] = inventory.book.publish_date
            inventory_dict['book_index_number'] = inventory.book.index_number
            inventory_dict['book_category_number'] = inventory.book.category.category_number
            inventory_dict['book_category_name'] = inventory.book.category.name
            inventory_dict['status'] = inventory.get_status_display()
            inventory_list.append(inventory_dict)
        return JsonResponse({'success': True, 'keyword': keywords, 'inventories': inventory_list, 'page_count': page_count, 'count': count}, status=200)
    else:
        return render(request, 'admin/inventory_list.html')

@admin_only
def add_inventory(request):
    if request.method == 'POST':
        book = Book.objects.get(id=request.POST['book_id'])
        status = request.POST['status']
        if status not in ['-1','0', '1']:
            return JsonResponse({'success': False, 'error': 'Invalid status'})
        location = request.POST['location']
        try:
            Inventory.objects.create(book=book, status=status, location=location)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
        return JsonResponse({'success': True})
    else:
        return render(request, 'admin/shard/inventory/add.html')

@admin_only
def add_inventories_bulk(request):
    if request.method == 'POST':
        csv_file = request.FILES['inventories_file']
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({'success': False, 'error': 'File type error'})
        file_data = csv_file.read().decode("utf-8")
        valid, reason = upload_validator.inventory_validate(file_data)
        if not valid:
            return JsonResponse({'success': False, 'error': reason})
        lines = file_data.split("\n")
        for line in lines:
            fields = line.split(",")
            book = Book.objects.get(id=fields[0])
            try:
                Inventory.objects.create(book=book, status=fields[1], location=fields[2])
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})
        return JsonResponse({'success': True})
    else:
        return render(request, 'admin/shard/inventory/add_bulk.html')
    
@admin_only
def edit_inventory(request):
    if request.method == 'POST':
        try:
            inventory = Inventory.objects.get(id=request.POST['inventory_id'])
            status = request.POST['status']
            # status处理：borrow=2时不可修改status，borrow!=2时只可在-1,0,1之间修改
            if inventory.status == 2 and status != '2':
                return JsonResponse({'success': False, 'error': 'Invalid status'})
            elif inventory.status != 2:
                if status not in ['-1','0', '1']:
                    return JsonResponse({'success': False, 'error': 'Invalid status'})
                inventory.status = status
            
            inventory.location = request.POST['location']
            inventory.save()
            return JsonResponse({'success': True})
        except ObjectDoesNotExist:
            return JsonResponse({'success': False, 'error': 'Inventory not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    else:
        try:
            inventory = Inventory.objects.get(id=request.GET['inventory_id'])
            return render(request, 'admin/shard/inventory/edit.html', {'inventory': inventory})
        except ObjectDoesNotExist:
            return JsonResponse({'success': False, 'error': 'Inventory not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
        
@admin_only
def delete_inventory(request):
    try:
        inventory = Inventory.objects.get(id=request.POST['inventory_id'])
        # 删除库存记录前需要检查是否有借阅记录
        if BorrowRecord.objects.filter(inventory=inventory).count() > 0:
            return JsonResponse({'success': False, 'error': 'There are borrow records for this inventory'})
        inventory.delete()
        return JsonResponse({'success': True})
    except ObjectDoesNotExist:
        return JsonResponse({'success': False, 'error': 'Inventory not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# 借阅记录视图
@admin_only
def borrow_record_list(request):
    # 搜索功能
    if request.method == 'POST':
        keyword = request.POST['keyword']
        # 拆解关键字，按空格分开，分别匹配
        keywords = keyword.split(' ')
        # 任意字段匹配搜索
        records = BorrowRecord.objects.none()
        for keyword in keywords:
            records = records | BorrowRecord.objects.filter(
                Q(reader__user__username__contains=keyword) |
                Q(reader__user__email__contains=keyword) |
                Q(inventory__book__title__contains=keyword) |
                Q(inventory__book__index_number__contains=keyword) |
                Q(borrow_date__contains=keyword) |
                Q(return_date__contains=keyword) |
                Q(status__contains=keyword)
            )
        records, count, page_count = paginate(request, records)
        # 添加分类号解析成名字的字段
        # 添加库存记录数字段
        record_list = []
        for record in records:
            record_dict = model_to_dict(record)
            record_dict['reader_username'] = record.reader.user.username
            record_dict['reader_email'] = record.reader.user.email
            record_dict['book_title'] = record.inventory.book.title
            record_dict['book_index_number'] = record.inventory.book.index_number
            record_dict['borrow_date'] = record.borrow_date.strftime('%Y-%m-%d')
            record_dict['return_date'] = record.return_date.strftime('%Y-%m-%d')
            record_dict['status'] = record.get_status_display()
            record_list.append(record_dict)
        return JsonResponse({'success': True, 'keyword': keywords, 'records': record_list, 'page_count': page_count, 'count': count}, status=200)
    else:
        return render(request, 'admin/borrow_record_list.html')

# 操作日志视图
@admin_only
def operation_log_list(request):
    # 搜索功能
    if request.method == 'POST':
        keyword = request.POST['keyword']
        # 拆解关键字，按空格分开，分别匹配
        keywords = keyword.split(' ')
        # 任意字段匹配搜索
        logs = OperationLog.objects.none()
        for keyword in keywords:
            logs = logs | OperationLog.objects.filter(
                Q(operator__username__contains=keyword) |
                Q(operator__email__contains=keyword) |
                Q(content__contains=keyword) |
                Q(operation_type__contains=keyword) |
                Q(timestamp__contains=keyword)
            )
        logs, count, page_count = paginate(request, logs)
        # 添加分类号解析成名字的字段
        # 添加库存记录数字段
        log_list = []
        for log in logs:
            log_dict = model_to_dict(log)
            log_dict['username'] = log.operator.username
            log_dict['user_email'] = log.operator.email
            log_dict['time'] = log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            log_list.append(log_dict)
        return JsonResponse({'success': True, 'keyword': keywords, 'logs': log_list, 'page_count': page_count, 'count': count}, status=200)
    else:
        return render(request, 'admin/operation_log_list.html')

# ----[触发器/signal]----

# 主要是借阅记录状态变化时，记录操作日志
@receiver(post_save, sender=BorrowRecord)
def log_borrow_record_save(sender, instance, created, **kwargs):
    operation_type = 'create' if created else 'update'
    content = f'{operation_type} a BorrowRecord instance: #{instance.id}'
    operator = instance.reader.user  # 假设Reader模型有一个user字段记录操作者
    OperationLog.log(operation_type, content, operator)

# 虽然正常情况下不会删除借阅记录，但是确保一下
@receiver(post_delete, sender=BorrowRecord)
def log_borrow_record_delete(sender, instance, **kwargs):
    operation_type = 'delete'
    content = f'{operation_type} a BorrowRecord instance'
    operator = instance.reader.user  # 假设Reader模型有一个user字段记录操作者
    OperationLog.log(operation_type, content, operator)

@receiver(post_save, sender=Inventory)
def log_inventory_save(sender, instance, created, **kwargs):
    operation_type = 'create' if created else 'update'
    content = f'{operation_type} a Inventory instance: #{instance.id}'
    operator = instance.last_borrowed_by.user
    OperationLog.log(operation_type, content, operator)

@receiver(post_delete, sender=Inventory)
def log_inventory_delete(sender, instance, **kwargs):
    operation_type = 'delete'
    content = f'{operation_type} a Inventory instance'
    operator = instance.last_borrowed_by.user
    OperationLog.log(operation_type, content, operator)

@receiver(post_save, sender=Book)
def log_book_save(sender, instance, created, **kwargs):
    operation_type = 'create' if created else 'update'
    content = f'{operation_type} a Book instance: #{instance.id}'
    operator = User.objects.get(username='admin')
    OperationLog.log(operation_type, content, operator)

@receiver(post_delete, sender=Book)
def log_book_delete(sender, instance, **kwargs):
    operation_type = 'delete'
    content = f'{operation_type} a Book instance'
    operator = User.objects.get(username='admin')
    OperationLog.log(operation_type, content, operator)

@receiver(post_save, sender=Category)
def log_category_save(sender, instance, created, **kwargs):
    operation_type = 'create' if created else 'update'
    content = f'{operation_type} a Category instance: #{instance.id}'
    operator = User.objects.get(username='admin')
    OperationLog.log(operation_type, content, operator)

@receiver(post_delete, sender=Category)
def log_category_delete(sender, instance, **kwargs):
    operation_type = 'delete'
    content = f'{operation_type} a Category instance'
    operator = User.objects.get(username='admin')
    OperationLog.log(operation_type, content, operator)

@receiver(post_save, sender=Reader)
def log_reader_save(sender, instance, created, **kwargs):
    operation_type = 'create' if created else 'update'
    content = f'{operation_type} a Reader instance: #{instance.id}'
    operator = instance.user
    OperationLog.log(operation_type, content, operator)

@receiver(post_delete, sender=Reader)
def log_reader_delete(sender, instance, **kwargs):
    operation_type = 'delete'
    content = f'{operation_type} a Reader instance'
    operator = instance.user
    OperationLog.log(operation_type, content, operator)

@receiver(post_save, sender=User)
def log_user_save(sender, instance, created, **kwargs):
    operation_type = 'create' if created else 'update'
    content = f'{operation_type} a User instance: #{instance.id}'
    operator = instance
    OperationLog.log(operation_type, content, operator)

@receiver(post_delete, sender=User)
def log_user_delete(sender, instance, **kwargs):
    operation_type = 'delete'
    content = f'{operation_type} a User instance'
    operator = instance
    OperationLog.log(operation_type, content, operator)
    