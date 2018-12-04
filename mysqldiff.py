# -*- coding: utf-8 -*-

# @Time    : 2018/11/23 13:59
# @Author  : zhoukang
# @File    : db_scan.py
"""
命令格式：python mysqldiff.py -x s=clear:123456@192.168.18.149:3306 db_new:db_old file=diff.sql
参数说明：
    -x：是否执行sql语句
    s=[user]:[pass]@[host]:[port]   ：当两个数据库的连接配置相同时可以用"s"参数
        user：用户名
        pass：密码
        host：ip地址
        port：端口
    so=[user]:[pass]@[host]:[port]  ：数据库配置
    sn=[user]:[pass]@[host]:[port]  ：被参照的数据库配置
    [db_new]{.[table_name]}:[db_old]{.[table_name]}   : 数据库名.表名
    file=[diff_file]   : 差异化sql保存位置
"""


import web
import os
import sys

reload(sys)
sys.setdefaultencoding("utf-8")


def connect(host, db, user='clear', pw='123456', port=3306):
    return web.database(
        dbn='mysql',
        host=host,
        port=int(port),
        db=db,
        user=user,
        pw=pw,
        charset='utf8'
    )


class Parameter(object):

    def __init__(self):
        self.user = None
        self.pw = None
        self.host = None
        self.port = None
        self.name = None
        self.table = None

    def build(self, command):
        p = command.split('@')
        self.user, self.pw = p[0].split(':')
        self.host, self.port = p[1].split(':')

    def valid(self):
        return not (self.user is None or self.pw is None or self.host is None
                    or self.port is None or self.name is None)

    def __str__(self):
        return str([self.user, self.pw, self.host, self.port, self.name, self.table])


# commands
command_exec = '-x'
command_copy = '-c'
command_db = 's'
command_db_new = 'sn'
command_db_old = 'so'
command_diff_file = 'file'

# params
is_exec_sql = False
is_copy_data = False
is_close_fk = False
diff_file_path = 'diff.sql'
exec_log_path = 'error.log'
db_new_param = Parameter()
db_old_param = Parameter()
args = sys.argv[1:]
print args
if len(args) < 2:
    print u"至少需要3个参数"
    exit(0)

# 判断是否立即执行sql语句
if command_exec in args:
    is_exec_sql = True
    args.remove(command_exec)

# 是否同步拷贝数据
if command_copy in args:
    is_copy_data = True
    args.remove(command_copy)


for item in args:
    if item.find('=') > 0:
        params = item.split('=')
        if params[0] == command_db:
            db_new_param.build(params[1])
            db_old_param.build(params[1])
        elif params[0] == command_db_new:
            db_new_param.build(params[1])
        elif params[0] == command_db_old:
            db_old_param.build(params[1])
        elif params[0] == command_diff_file:
            diff_file_path = params[1]
    elif item.find(':') > 0:
        params = item.split(':')
        if params[0].find('.') >= 0:
            db_new_param.name, db_new_param.table = params[0].split('.')
            db_old_param.name, db_old_param.table = params[1].split('.')
        else:
            db_new_param.name = params[0]
            db_old_param.name = params[1]

if not db_new_param.valid() or not db_old_param.valid():
    print u'参数无效'
    exit()

print u'是否立即执行sql语句：', is_exec_sql
print u'新数据库：', db_new_param
print u'旧数据库：', db_old_param
print u'diff保存位置：', diff_file_path

if os.path.exists(diff_file_path):
    os.remove(diff_file_path)
if os.path.exists(exec_log_path):
    os.remove(exec_log_path)
diff_file = open(diff_file_path, 'a+')
log_file = open(exec_log_path, 'a+')

# db_name_new = 'ims_default'
# db_name_old = 'ims_default'
db_new = connect(db_new_param.host, db_new_param.name, port=db_new_param.port,
                 user=db_new_param.user, pw=db_new_param.pw)
db_old = connect(db_old_param.host, db_old_param.name, port=db_old_param.port,
                 user=db_old_param.user, pw=db_old_param.pw)


def print_data(data):
    if isinstance(data, web.IterBetter):
        print '=' * 50
        for item in data:
            print item
        print '*' * 50
        print ''
        return
    print data


def exists(db, table):
    res = db.query("show tables like '%s'" % str(table))
    return True if len(res) > 0 else False


def get_table_structure(db, table):
    """获取创建表DDL语句"""
    res = db.query("show create table %s" % table)
    for item in res:
        return item['Create Table'] + ';'


def desc(db, table):
    return db.query('desc %s' % table)


def q(x): return "(" + x + ")"


def pipe(db_new, db_old, table):
    """新表中默认数据的insert语句"""
    res = db_new.query('select * from %s' % table)
    if len(res) <= 0:
        return
    values = []
    keys = None
    for item in res:
        # TODO 导入默认数据
        _keys = web.SQLQuery.join(item.keys(), ', ')
        _values = web.SQLQuery.join([web.sqlparam(v) for v in item.values()], ', ')
        if keys is None:
            keys = (q(_keys))
        values.append(unicode(q(_values)))
    return "INSERT INTO %s " % table + keys + ' VALUES \n\t' + ', \n\t'.join(values) + ';'


def get_field(fields, field_name):
    for item in fields:
        if field_name == item['Field']:
            return item


def compare_field(field_new, field_old):
    """属性比较"""
    return field_new.__eq__(field_old)


def delete_table(db, table):
    """删除表"""
    print '删除表: ', table
    db.query('drop table %s' % table)


def build_default_sql(default_new, default_old):
    if default_new is None:
        return ''
    if isinstance(default_new, str):
        return "DEFAULT '%s'" % default_new
    else:
        return "DEFAULT %s" % default_new


def build_null_sql(null_new, null_old):
    if null_new == 'YES':
        return 'NULL'
    else:
        return 'NOT NULL'


def build_base_field(new, old):
    # print_data(new)
    return ('`%s` %s %s %s %s' % (
        new['Field'], new['Type'], build_default_sql(new['Default'], None if old is None else old['Default']),
        build_null_sql(new['Null'], None if old is None else old['Null']), new['Extra']))


def build_change_sql(new, old):
    """VARCHAR(125) CHARSET utf8 COLLATE utf8_unicode_ci DEFAULT '' NOT NULL COMMENT '姓名',"""
    return 'CHANGE ' + build_base_field(new, old)


def build_add_sql(new, old):
    """ADD COLUMN `age` INT(11) UNSIGNED DEFAULT 0 NOT NULL AFTER `name`, """
    return 'ADD COLUMN ' + build_base_field(new, old)


def build_drop_col_sql(field):
    return 'DROP COLUMN `%s`' % field['Field']


def build_alter_table_sql(fields_new, fields_old):
    change_sql = []
    add_sql = []
    drop_col_sql = []
    key_sql = []
    for item in fields_new:
        old = get_field(fields_old, item['Field'])
        # 新增字段
        if old is None:
            add_sql.append(build_add_sql(item, old))
            continue
        if item.__eq__(old):
            continue
        # 修改
        if item['Type'] != old['Type'] or cmp(item['Default'] != 0, old['Default']) or item['Extra'] != old['Extra'] or \
                        item['Null'] != old['Null']:
            change_sql.append(build_change_sql(item, old))
    for item in fields_old:
        if get_field(fields_new, item['Field']) is None:
            drop_col_sql.append(build_drop_col_sql(item))
    # 主键判断
    pri_keys_new = map(lambda y: y['Field'], filter(lambda x: x['Key'] == 'PRI', fields_new))
    pri_keys_old = map(lambda y: y['Field'], filter(lambda x: x['Key'] == 'PRI', fields_old))
    if not pri_keys_new.__eq__(pri_keys_old):
        # 主键不相同
        key_sql.append('DROP PRIMARY KEY')
        if len(pri_keys_new) > 0:
            key_sql.append('ADD PRIMARY KEY (`%s`)' % '`,`'.join(pri_keys_new))
    return drop_col_sql + add_sql + change_sql + key_sql


def get_foriegn_keys(db, db_name):
    """获取数据的所有外键约束"""
    return db.query(
        'SELECT DISTINCT C.TABLE_SCHEMA, '
        'C.REFERENCED_TABLE_NAME, '
        'C.REFERENCED_COLUMN_NAME, '
        'C.TABLE_NAME, '
        'C.COLUMN_NAME, '
        'C.CONSTRAINT_NAME, '
        'T.TABLE_COMMENT, '
        'R.UPDATE_RULE, '
        'R.DELETE_RULE '
        'FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE C '
        'JOIN INFORMATION_SCHEMA.TABLES T ON T.TABLE_NAME = C.TABLE_NAME '
        'JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS R ON R.TABLE_NAME = C.TABLE_NAME '
        'AND R.CONSTRAINT_NAME = C.CONSTRAINT_NAME '
        'AND R.REFERENCED_TABLE_NAME = C.REFERENCED_TABLE_NAME '
        'WHERE C.TABLE_SCHEMA=$db_name AND C.REFERENCED_TABLE_NAME IS NOT NULL',
        vars={'db_name': db_name})


def get_foriegn_key(fks, fk_name):
    for item in fks:
        if item['CONSTRAINT_NAME'] == fk_name:
            return item


def build_base_fk_sql(fk):
    return ("ALTER TABLE `%s` ADD CONSTRAINT `%s` FOREIGN KEY (`%s`) REFERENCES `%s`(`%s`) ON UPDATE %s ON DELETE %s;" %
            (fk['TABLE_NAME'], fk['CONSTRAINT_NAME'], fk['COLUMN_NAME'],
             fk['REFERENCED_TABLE_NAME'], fk['REFERENCED_COLUMN_NAME'], fk['UPDATE_RULE'], fk['DELETE_RULE']))


def build_add_fk_sql(fk):
    """
    添加外键约束
    ALTER TABLE `db_new`.`course`
    ADD CONSTRAINT `fk_name` FOREIGN KEY (`user_id`) REFERENCES `db_new`.`user`(`id`) ON UPDATE CASCADE ON DELETE NO ACTION,
    DROP FOREIGN KEY `fk`;
    """
    return build_base_fk_sql(fk)


def build_update_fk_sql(fk_new, fk_old):
    """修改外键"""
    return build_base_fk_sql(fk_new)


def build_delete_fk_sql(fk):
    """删除外键"""
    return "ALTER TABLE `%s` DROP FOREIGN KEY `%s`;" % (fk['TABLE_NAME'], fk['CONSTRAINT_NAME'])


def build_foriegn_key_sqls(db_new, db_name_new, db_old, db_name_old):
    """删除外键约束"""
    print u"外键操作"
    foriegn_keys_new = get_foriegn_keys(db_new, db_name_new)
    foriegn_keys_old = get_foriegn_keys(db_old, db_name_old)
    print_data(foriegn_keys_new)
    print_data(foriegn_keys_old)
    delete_fks = []
    update_fks = []
    add_fks = []
    for fk_new in foriegn_keys_new:
        fk_old = get_foriegn_key(foriegn_keys_old, fk_new['CONSTRAINT_NAME'])
        if fk_old is None:
            add_fks.append(build_add_fk_sql(fk_new))
            continue
        if compare_foriegn_key(fk_new, fk_old):
            continue
        delete_fks.append(build_delete_fk_sql(fk_new))
        update_fks.append(build_update_fk_sql(fk_new, fk_old))
    for fk_old in foriegn_keys_old:
        if get_foriegn_key(foriegn_keys_new, fk_old['CONSTRAINT_NAME']) is None:
            delete_fks.append(build_delete_fk_sql(fk_old))
    return delete_fks, update_fks + add_fks


def file_append(file, table_name, *sqls):
    """文件中追加内容"""
    if sqls is None or len(sqls) == 0:
        return
    file.write('/' + '*' * 30 + ' ' + table_name + ' ' + '*' * 30 + '/')
    file.write('\n')
    for item in sqls:
        print type(item)
        print_data(item)
        file.write(unicode(item))
        file.write('\n')
        file.write('\n')


def show_error_log(db):
    res = db.query('SHOW WARNINGS')
    for i in res:
        return '%s:%s %s' % (i['Level'], i['Code'], i['Message'])


def ex(db, *sqls):
    for sql in sqls:
        try:
            db.query(sql)
        except Exception, e:
            print e
            log_file.write('*' * 50)
            log_file.write('\n')
            log_file.write(sql)
            log_file.write('\n')
            log_file.write(show_error_log(db))
            log_file.write('\n')
            log_file.write('\n')


def handle_sql(db, title, *sqls):
    if sqls is None or len(sqls) == 0:
        return
    # save
    file_append(diff_file, title, *sqls)
    if not is_exec_sql:
        return
    # exec
    ex(db, *sqls)


def show_tables(db, db_name, table_like=None):
    if table_like is None:
        return 'Tables_in_' + db_name, db.query('SHOW TABLES')
    else:
        return 'Tables_in_%s %s' % (db_name, q(table_like)), db.query("SHOW TABLES LIKE '%s'" % db_name)


def compare_table_structure(new_table_name, old_table_name):
    fields_new = list(desc(db_new, new_table_name))
    fields_old = list(desc(db_old, old_table_name))
    # 表结构相同
    if fields_new.__eq__(fields_old):
        return
    alter_sql = build_alter_table_sql(fields_new, fields_old)
    if len(alter_sql) == 0:
        return
    return ('ALTER TABLE %s \n\t' % old_table_name) + ', \n\t'.join(alter_sql) + ';'


def compare_foriegn_key(fk, other_fk):
    for key, value in fk:
        if key == 'TABLE_SCHEMA' or key == 'TABLE_COMMENT':
            continue
        if cmp(value, other_fk[key]) != 0:
            return False
    return True


def start():
    handle_sql(db_old, u'关闭外键约束', 'SET FOREIGN_KEY_CHECKS=0;')
    # 外键约束
    delete_fks, add_fks = build_foriegn_key_sqls(db_new, db_new_param.name, db_old, db_old_param.name)
    # tables_new = db_new.query('show tables')
    key, tables_new = show_tables(db_new, db_new_param.name, db_new_param.table)
    # 新表
    for item in tables_new:
        print item
        table_name = item[key]
        # 1, 表不存在，需要新建
        if not exists(db_old, table_name):
            # 表不存在
            sqls = []
            sql_create_table = get_table_structure(db_new, table_name)
            if len(add_fks) > 0 and sql_create_table.find('CONSTRAINT') > 0:
                add_fks = filter(lambda x: x.find('ALTER TABLE `%s`' % table_name) < 0, add_fks)
            sqls.append(sql_create_table)
            # 开始导入默认的数据
            if is_copy_data:
                insert_sql = pipe(db_new, db_old, table_name)
                if insert_sql is not None:
                    sqls.append(insert_sql)
            handle_sql(db_old, table_name, *sqls)
            continue

        # 2, 表存在，则判断字段
        fields_new = list(desc(db_new, table_name))
        fields_old = list(desc(db_old, table_name))
        # 表结构相同
        if fields_new.__eq__(fields_old):
            continue
        alter_sql = build_alter_table_sql(fields_new, fields_old)
        if len(alter_sql) == 0:
            continue
        sql = ('ALTER TABLE %s \n\t' % table_name) + ', \n\t'.join(alter_sql) + ';'
        # sql = compare_fields(table_name, table_name)
        handle_sql(db_old, table_name, sql)
    handle_sql(db_old, 'delete foreign key', *delete_fks)
    handle_sql(db_old, 'add foreign key', *add_fks)
    handle_sql(db_old, u'开启外键约束', 'SET FOREIGN_KEY_CHECKS=1;')


if __name__ == '__main__':
    if db_new_param.table is not None:
        sql = compare_table_structure(db_new_param.table, db_old_param.table)
        handle_sql(db_old, db_old_param.table, sql)
        exit()
    try:
        start()
    except Exception, e:
        print e
    finally:
        diff_file.close()
        log_file.close()
