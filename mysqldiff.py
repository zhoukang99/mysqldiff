# -*- coding: utf-8 -*-

# @Time    : 2018/11/23 13:59
# @Author  : zhoukang
# @File    : mysqldiff.py
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
import datetime
import web
import os
import sys
import traceback

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


class MapParser(object):
    """映射关系配置文件解析"""

    def __init__(self):
        self.old_table = None
        self.old_cols = []
        self.new_table = None
        self.new_cols = []
        self.line = None
        self.map_data = False

    def parse(self, line):
        """
        oldtable -> newtable
        oldtable.oldcol -> newtable.newcol
        oldtable.[oldcol1, oldcol12, oldcol3 ......] -> newtable.[newcol1, newcol2, newcol3 ......]
        :param line:
        :return: [sql1, sql2, ......]
        """
        line = line.replace(' ', '')
        print line
        if len(line) == 0:
            return []
        sign = '=>'
        if line.find(sign) > 0:
            self.map_data = True
        elif line.find('->') > 0:
            sign = '->'
        else:
            raise BaseException(u'格式错误：' + line)
        old, new = line.split(sign)
        if old.__eq__(new):
            return []
        self.line = line
        parse_success = False
        if old.find('.') < 0 and new.find('.') < 0:
            self.old_table = old
            self.new_table = new
            parse_success = True
        elif old.find('.[') > 0 and new.find('.[') > 0:
            self.old_table, old_cols_str = old.split('.')
            self.new_table, new_cols_str = new.split('.')
            old_cols_str = old_cols_str.replace('[', '')
            old_cols_str = old_cols_str.replace(']', '')
            new_cols_str = new_cols_str.replace('[', '')
            new_cols_str = new_cols_str.replace(']', '')
            self.old_cols = old_cols_str.split(',')
            self.new_cols = new_cols_str.split(',')
            parse_success = True
        elif old.find('.') > 0 and new.find('.') > 0:
            self.old_table, old_col = old.split('.')
            self.new_table, new_col = new.split('.')
            self.old_cols.append(old_col)
            self.new_cols.append(new_col)
            parse_success = True
        if parse_success and self.check():
            return True
        raise BaseException(u'格式错误：' + line)

    def check(self):
        if len(self.old_cols) != len(self.new_cols):
            raise BaseException(u'列的个数不一致：' + self.line)
        if self.map_data and self.old_table == self.new_table:
            raise BaseException(u'数据导入时表名不能相同：' + self.line)
        if not self.map_data and len(self.old_cols) > 0 and self.old_cols.__eq__(self.new_cols):
            self.old_cols = []
            self.new_cols = []
        return True

    def build_raname(self):
        """
        重命名
        """
        sqls = []
        if len(self.new_cols) > 0:
            for i, col in enumerate(self.old_cols):
                sqls.append(r'ALTER TABLE `%s` CHANGE `%s` `%s`;' % (self.old_table, col, self.new_cols[i]))
        if self.new_table != self.old_table:
            sqls.append('ALTER TABLE `%s` RENAME TO `%s`;' % (self.old_table, self.new_table))
        return sqls

    def build_pipe(self):
        """
        导入数据
        _values = unicode(', '.join([safestr(v) for v in item.values()]))
        values.append(q(_values))
        """
        if self.old_table == self.new_table:
            return []
        sqls = []
        old_keys = '*'
        new_keys = None
        if len(self.new_cols) > 0:
            old_keys = ','.join(self.old_cols)
            new_keys = q('`' + '`,`'.join(self.new_cols) + '`')
        res = db_old.query('SELECT %s FROM %s' % (old_keys, self.old_table))
        if len(res) <= 0:
            return []
        values = []
        for i, item in enumerate(res):
            if new_keys is None:
                _keys = web.SQLQuery.join(item.keys(), '`, `')
                new_keys = (q('`' + _keys + '`'))
            # _values = web.SQLQuery.join([web.sqlparam(v) for v in item.values()], ', ')
            _values = (', '.join([safestr(v) for v in item.values()]))
            values.append(q(_values))
        sqls.append("INSERT INTO %s " % self.new_table + new_keys + ' VALUES \n\t' + ', \n'.join(values) + ';')
        return sqls

    def build(self):
        if self.map_data:
            return self.build_pipe()
        else:
            return self.build_raname()


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
map_config_path = 'map.config'
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


def check_map(parser):
    if db_new_param.table is not None:
        if parser.new_table != db_new_param.table and parser.old_table != db_old_param.table:
            return False
    exists_new_table = exists(db_old, parser.new_table)
    if not parser.map_data:
        # 重命名
        if not exists_new_table:
            return True
        if len(parser.new_cols) == 0:
            # 表已重命名过
            return False
        else:
            # 判断列是否重命名
            fields = desc(db_old, parser.new_table)
            count = 0
            for col in parser.new_cols:
                if len(filter(lambda x: x['Field'] == col, fields)) > 0:
                    count += 1
            if count == 0:
                return True
            elif count == len(parser.new_cols):
                return False
            else:
                raise BaseException(u'列名存在冲突：' + parser.line)
    else:
        # 导入数据
        if exists_new_table:
            return False
        return True


def parse_map_config(config_path):
    """
    map.config文件解析称对应的sql语句
    :param config_path:
    :return:
    """
    if not os.path.exists(config_path):
        return [], []
    rename_parsers = []
    pipe_parsers = []
    # rename_sqls = []
    # pipe_sqls = []
    map_file = open(config_path)
    for line in map_file:
        line = line.strip()
        if len(line) <= 0 or line.replace(' ', '').startswith('#') or line.find('->') <= 0 and line.find('=>') <= 0:
            continue
        parser = MapParser()
        parser.parse(line)
        # 判断表格是否已经导入和创建了
        if not check_map(parser):
            continue
        # sqls = parser.build()
        # if len(sqls) == 0:
        #     continue
        if parser.map_data:
            pipe_parsers.append(parser)
            # pipe_sqls.extend(sqls)
        else:
            # rename_sqls.extend(sqls)
            rename_parsers.append(parser)
    map_file.close()
    # return rename_sqls, pipe_sqls
    return rename_parsers, pipe_parsers


def build_map_sqls(parsers):
    if parsers is None or len(parsers) == 0:
        return []
    sqls = []
    for p in parsers:
        sqls.extend(p.build())
    return sqls


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


def sqlify(obj):
    """
    converts `obj` to its proper SQL version

        >>> sqlify(None)
        'NULL'
        >>> sqlify(True)
        "'t'"
        >>> sqlify(3)
        '3'
    """
    # because `1 == True and hash(1) == hash(True)`
    # we have to do this the hard way...

    if obj is None:
        return 'NULL'
    elif obj is True:
        return "'t'"
    elif obj is False:
        return "'f'"
    elif isinstance(obj, long):
        return str(obj)
    elif datetime and isinstance(obj, datetime.datetime):
        return repr(obj.isoformat())
    else:
        if isinstance(obj, unicode): obj = obj.encode('utf8')
        return repr(obj)


def safestr(obj, encoding='utf-8'):
    r"""
    Converts any given object to utf-8 encoded string.

        >>> safestr('hello')
        'hello'
        >>> safestr(u'\u1234')
        '\xe1\x88\xb4'
        >>> safestr(2)
        '2'
    """
    # print type(obj), obj
    if obj is None:
        return 'NULL'
    elif obj is True:
        return "'t'"
    elif obj is False:
        return "'f'"
    elif isinstance(obj, long):
        return str(obj)
    elif isinstance(obj, unicode):
        return my_repr_str(str(obj))
    elif isinstance(obj, str):
        return my_repr_str(obj)
    elif isinstance(obj, datetime.datetime):
        return "'" + str(obj) + "'"
    else:
        return repr(str(obj))


def my_repr_str(obj):
    if isinstance(obj, str):
        obj = obj.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")
    return "'%s'" % obj


def pipe(db_new, db_old, table):
    """新表中默认数据的insert语句"""
    res = db_new.query('select * from %s' % table)
    if len(res) <= 0:
        return
    values = ''
    keys = None
    for i, item in enumerate(res):
        # TODO 导入默认数据
        if keys is None:
            _keys = '`, `'.join(item.keys())
            keys = str(q('`' + _keys + '`'))
        # _values = str(web.SQLQuery.join([web.sqlparam(v) for v in item.values()], ', '))
        _values = (', '.join([safestr(v) for v in item.values()]))
        # handle_sql(db_old, '', q(_values))
        # print type(_values), _values
        # values.append(q(_values))
        if i != 0:
            values += ', \n'
        values += q(_values)
    # return "INSERT INTO %s " % table + keys + ' VALUES \n' + ', \n'.join(values) + ';'
    return "INSERT INTO %s " % str(table) + keys + ' VALUES \n' + values + ';'


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
    return "DEFAULT %s" % safestr(default_new)


def build_null_sql(null_new, null_old):
    if null_new == 'YES':
        return 'NULL'
    else:
        return 'NOT NULL'


def build_base_field(new, old):
    # print_data(new)
    return ('`%s` %s %s %s %s' % (
        new['Field'], new['Type'],
        build_null_sql(new['Null'], None if old is None else old['Null']),
        build_default_sql(new['Default'], None if old is None else old['Default']),
        new['Extra']))


def build_change_sql(new, old):
    """VARCHAR(125) CHARSET utf8 COLLATE utf8_unicode_ci DEFAULT '' NOT NULL COMMENT '姓名',"""
    return 'MODIFY ' + build_base_field(new, old)


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
        # 修改
        if item['Type'] != old['Type'] or cmp(item['Default'], old['Default']) != 0 or item['Extra'] != old['Extra'] or \
                        item['Null'] != old['Null']:
            print item
            print old
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
    # file.write('/' + '*' * 30 + ' ' + table_name + ' ' + '*' * 30 + '/')
    file.write('/' + table_name.center(80, '*') + '/')
    file.write('\n')
    for s in sqls:
        # print s
        file.write(s)
        file.write('\n')
        file.write('\n')


def show_error_log(db):
    res = db.query('SHOW WARNINGS')
    for i in res:
        return '%s:%s %s' % (i['Level'], i['Code'], i['Message'])
    return ''


def ex(db, *sqls):
    for sql in sqls:
        try:
            db.query(web.SQLQuery.join(sql, ''), processed=True)
        except Exception as exception:
            print sql
            traceback.print_exc()
            log_file.write('*' * 50)
            log_file.write('\n')
            log_file.write(sql)
            log_file.write('\n')
            log_file.write(show_error_log(db))
            log_file.write('\n')
            log_file.write('\n')
            raise exception


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


def filter_rename_table(table, parsers):
    """
    过滤重命名的表格
    :param table:
    :param parsers:
    :return:
    """
    for p in parsers:
        if p.new_table == table and p.new_table != p.old_table:
            return p.old_table
    return table


def filter_rename_field(table, fields, parsers):
    """
    由于重命名sql在前面执行，所以需要根据重命名配置过滤字段
    :param fields:
    :param parsers:
    :return:
    """
    for p in parsers:
        if p.map_data or table != p.old_table:
            continue
        if len(p.new_cols) == 0:
            return fields
        for f in fields:
            if f['Field'] in p.old_cols:
                i = p.old_cols.index(f['Field'])
                f['Field'] = p.new_cols[i]
        break
    return fields


def start():
    handle_sql(db_old, u'关闭外键约束', 'SET FOREIGN_KEY_CHECKS=0;')
    rename_parsers, pipe_parsers = parse_map_config(map_config_path)
    # rename_sqls, pipe_sqls = parse_map_config(map_config_path)
    sql_renames = build_map_sqls(rename_parsers)
    sql_pipes = build_map_sqls(pipe_parsers)
    handle_sql(db_old, u'表或列重命名', *sql_renames)
    # 外键约束
    sql_delete_fks, sql_add_fks = build_foriegn_key_sqls(db_new, db_new_param.name, db_old, db_old_param.name)
    # tables_new = db_new.query('show tables')
    key, tables_new = show_tables(db_new, db_new_param.name, db_new_param.table)
    # 新表
    sql_create_tables = []
    sql_alter_tables = []
    for item in tables_new:
        table_name = item[key]
        old_table_name = filter_rename_table(table_name, rename_parsers)
        # 1, 表不存在，需要新建
        if not exists(db_old, old_table_name):
            # 表不存在
            sql_create_table = get_table_structure(db_new, table_name)
            if len(sql_add_fks) > 0 and sql_create_table.find('CONSTRAINT') > 0:
                sql_add_fks = filter(lambda x: x.find('ALTER TABLE `%s`' % table_name) < 0, sql_add_fks)
            sql_create_tables.append(sql_create_table)
            # 开始导入默认的数据
            if is_copy_data:
                insert_sql = pipe(db_new, db_old, table_name)
                if insert_sql is not None:
                    sql_create_tables.append(insert_sql)
            continue
        # 2, 表存在，则判断字段
        fields_new = sorted(list(desc(db_new, table_name)), key=lambda x: x['Field'])
        fields_old = sorted(list(desc(db_old, old_table_name)), key=lambda x: x['Field'])
        # 过滤重命名设置
        filter_rename_field(old_table_name, fields_old, rename_parsers)
        # 表结构相同
        if fields_new.__eq__(fields_old):
            continue
        alter_sql = build_alter_table_sql(fields_new, fields_old)
        if len(alter_sql) == 0:
            continue
        sql = ('ALTER TABLE %s \n\t' % table_name) + ', \n\t'.join(alter_sql) + ';'
        # sql = compare_fields(table_name, table_name)
        # TODO 修改表
        # handle_sql(db_old, table_name, sql)
        sql_alter_tables.append(sql)
    handle_sql(db_old, u'新增表', *sql_create_tables)
    handle_sql(db_old, u'往新增表中导入旧表中数据', *sql_pipes)
    handle_sql(db_old, u'修改', *sql_alter_tables)
    handle_sql(db_old, 'delete foreign key', *sql_delete_fks)
    handle_sql(db_old, 'add foreign key', *sql_add_fks)
    handle_sql(db_old, u'开启外键约束', 'SET FOREIGN_KEY_CHECKS=1;')


if __name__ == '__main__':
    if db_new_param.table is not None:
        sql = compare_table_structure(db_new_param.table, db_old_param.table)
        if not sql:
            handle_sql(db_old, db_old_param.table, sql)
        exit()
    transaction = db_old.transaction()
    try:
        start()
        print u'提交'
        transaction.commit()
    except Exception:
        print u'回滚'
        transaction.rollback()
        traceback.print_exc()
    finally:
        diff_file.close()
        log_file.close()
