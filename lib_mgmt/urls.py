from django.urls import path
from . import views

app_name = "lib"
urlpatterns = [
    # 首页
    path('', views.index, name='index'),

    # API
    path('api/user_borrow_stats/', views.UserBorrowStatsView.as_view(), name='user_borrow_stats'),
    path('api/top_borrowed_books/', views.TopBorrowedBooksView.as_view(), name='top_borrowed_books'),
    path('api/get_categories/', views.CategoryView.as_view(), name='get_categories'),
    path('api/get_books/', views.BookView.as_view(), name='get_books'),
   
    # 登录态
    path('auth/login/', views.user_login, name='user_login'),
    path('auth/register/', views.user_register, name='user_register'),
    path('auth/logout/', views.user_logout, name='user_logout'),
    
    # 用户态
    path('user/', views.user_center, name='user_center'),

    path('user/borrowed/', views.user_borrow_records, name='user_borrow_records'),
    path('user/search/', views.user_borrow_search, name='user_borrow_search'),
    path('user/book/', views.user_borrow_inv, name='user_borrow_inv'),
    path('user/borrow/commit/', views.user_borrow_book, name='user_borrow_book'),
    path('user/return/commit/', views.user_return_book, name='user_return_book'),

    path('user/profile/', views.user_view_profile, name='user_view_profile'),
    path('user/profile/edit', views.user_edit_profile, name='user_edit_profile'),
    path('user/profile/password', views.user_change_password, name='user_change_password'),

    # 管理态
    path('admin/', views.admin_center, name='admin_center'),

    path('admin/readers/', views.reader_list, name='reader_list'),
    path('admin/readers/add/', views.add_reader, name='add_reader'),
    path('admin/readers/add_bulk/', views.add_readers_bulk, name='add_readers_bulk'),
    path('admin/readers/edit/', views.edit_reader, name='edit_reader'),
    path('admin/readers/disable/', views.disable_reader, name='disable_reader'),
    path('admin/readers/enable/', views.enable_reader, name='enable_reader'),

    path('admin/books/', views.book_list, name='book_list'),
    path('admin/books/add/', views.add_book, name='add_book'),
    path('admin/books/add_bulk/', views.add_books_bulk, name='add_books_bulk'),
    path('admin/books/edit/', views.edit_book, name='edit_book'),
    path('admin/books/delete/', views.delete_book, name='delete_book'),

    path('admin/categories/', views.category_list, name='category_list'),
    path('admin/categories/add/', views.add_category, name='add_category'),
    path('admin/categories/add_bulk/', views.add_categories_bulk, name='add_categories_bulk'),
    path('admin/categories/edit/', views.edit_category, name='edit_category'),
    path('admin/categories/delete/', views.delete_category, name='delete_category'),

    path('admin/inventory/', views.inventory_list, name='inventory_list'),
    path('admin/inventory/add/', views.add_inventory, name='add_inventory'),
    path('admin/inventory/add_bulk/', views.add_inventories_bulk, name='add_inventories_bulk'),
    path('admin/inventory/edit/', views.edit_inventory, name='edit_inventory'),
    path('admin/inventory/delete/', views.delete_inventory, name='delete_inventory'),

    path('admin/borrow_records/', views.borrow_record_list, name='borrow_record_list'),
    path('admin/operation_logs/', views.operation_log_list, name='operation_log_list'),
]

