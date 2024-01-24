def book_validate(file_data):
    try:
        lines = file_data.split("\n")
        for line in lines:
            # 检查每一行是否有 7 个字段
            # 检查字段属性和长度是否符合要求
            # 不符合返回 (False,reason)
            fields = line.split(",")
            if len(fields) != 7:
                return (False, "Invalid number of fields")
            title = fields[0]
            author = fields[1]
            publisher = fields[2]
            publish_date = fields[3]
            index_number = fields[4]
            category = fields[5]
            description = fields[6]
            if len(title) > 100:
                return (False, "Title too long")
            if len(author) > 100:
                return (False, "Author too long")
            if len(publisher) > 100:
                return (False, "Publisher too long")
            if len(publish_date) > 100:
                return (False, "Publish date too long")
            if len(index_number) > 50:
                return (False, "Index number too long")
            if len(category) > 100:
                return (False, "Category too long")
            if description is None:
                description = ""
    except Exception as e:
        return (False, str(e))
    return (True, "good")

def category_validate(file_data):
    try:
        lines = file_data.split("\n")
        for line in lines:
            # 检查每一行是否有 2 个字段
            # 检查字段属性和长度是否符合要求
            # 不符合返回 (False,reason)
            fields = line.split(",")
            if len(fields) != 2:
                return (False, "Invalid number of fields")
            category_number = fields[0]
            name = fields[1]
            if len(category_number) > 50:
                return (False, "Category number too long")
            if len(name) > 100:
                return (False, "Name too long")
    except Exception as e:
        return (False, str(e))
    return (True, "good")

def inventory_validate(file_data):
    try:
        lines = file_data.split("\n")
        for line in lines:
            # 检查每一行是否有 5 个字段 或 last_borrowed_on 和 last_borrowed_by 共同为空
            # 检查字段属性和长度是否符合要求
            # 不符合返回 (False,reason)
            fields = line.split(",")
            length = len(fields)
            if length != 5 and (fields[3] != "" or fields[4] != ""):
                return (False, "Invalid number of fields")
            index_number = fields[0]
            status = fields[1]
            location = fields[2]    
            if length == 5:
                last_borrowed_on = fields[3]
                last_borrowed_by = fields[4]
            if len(index_number) > 50:
                return (False, "Index number too long")
            if len(status) > 1:
                return (False, "Status too long")
            if len(location) > 100:
                return (False, "Location too long")
            if length == 5:
                if len(last_borrowed_on) > 100:
                    return (False, "Last borrowed on too long")
                if len(last_borrowed_by) > 100:
                    return (False, "Last borrowed by too long")
    except Exception as e:
        return (False, str(e))
    return (True, "good")

def reader_validate(file_data):
    try:
        lines = file_data.split("\n")
        for line in lines:
            # 检查每一行是否有 7 个字段
            # 检查字段属性和长度是否符合要求
            # 不符合返回 (False,reason)
            fields = line.split(",")
            if len(fields) != 7:
                return (False, "Invalid number of fields")
            username = fields[0]
            first_name = fields[1]
            last_name = fields[2]
            email = fields[3]
            password = fields[4]
            is_staff = fields[5]
            max_borrow_limit = fields[6]
            if len(username) > 20:
                return (False, "Username too long")
            if len(first_name) > 30:
                return (False, "First name too long")
            if len(last_name) > 30:
                return (False, "Last name too long")
            if len(email) > 100:
                return (False, "Email too long")
            if len(password) > 25:
                return (False, "Password too long")
            if len(is_staff) > 1:
                return (False, "Is staff too long")
            if len(max_borrow_limit) > 10:
                return (False, "Max borrow limit too long")
    except Exception as e:
        return (False, str(e))
    return (True, "good")