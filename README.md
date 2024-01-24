# 图书馆馆藏管理系统
贡橙计科课设优秀课题，供学弟学妹们白嫖。

## 使用方法

1. 配置conda环境

```sh
conda env create -f conda-environment.yaml
conda activate db-design
```

2. 链接到你自己的数据库

修改 `db_design/settings.py` 中的 `DATABASES.default` 信息为自己的数据库 backend。

3. 生成数据库

```sh
python manage.py makemigrations
python manage.py migrate
```

4. 分配管理员

```sh
python manage.py createsuperuser
```

5. 启动系统

```sh
python manage.py runsevrer
```