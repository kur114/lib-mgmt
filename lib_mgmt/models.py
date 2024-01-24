from django.db import models
from django.contrib.auth.models import User
# Create your models here.

# 读者模型
class Reader(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    max_borrow_limit = models.IntegerField(default=5)

# 分类模型
class Category(models.Model):
    category_number = models.CharField(max_length=50)
    name = models.CharField(max_length=100)

# 图书模型
class Book(models.Model):
    title = models.CharField(max_length=100)
    author = models.CharField(max_length=100)
    publisher = models.CharField(max_length=100)
    publish_date = models.CharField(max_length=100)
    index_number = models.CharField(max_length=50)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    description = models.TextField(null=True, blank=True)

# 库存记录模型
class Inventory(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    status = models.IntegerField(default=1)
    location = models.CharField(max_length=100, blank=True, null=True)
    last_borrowed_on = models.DateField(blank=True, null=True)
    last_borrowed_by = models.ForeignKey(Reader, on_delete=models.SET_NULL, blank=True, null=True)

    STATUS_CHOICES = (
        (-1, "Removed"),
        (0, "Under Maintenance"),
        (1, "In Library"),
        (2, "Borrowed"),
    )
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "Unknown")

# 借阅记录模型
class BorrowRecord(models.Model):
    reader = models.ForeignKey(Reader, on_delete=models.CASCADE)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    borrow_date = models.DateField()
    return_date = models.DateField()
    status = models.IntegerField(default=1)

    STATUS_CHOICES = (
        (-1, "Overdue"),
        (0, "Returned"),
        (1, "Borrowed"),
    )
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "Unknown")
    
# 操作日志模型
class OperationLog(models.Model):
    operation_type = models.CharField(max_length=50)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)

    @classmethod
    def log(cls, operation_type, content, operator):
        log = cls(operation_type=operation_type, content=content, operator=operator)
        log.save()