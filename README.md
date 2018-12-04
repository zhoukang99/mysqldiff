&emsp;&emsp;**mysqldiff是一个能够方便于大家在实际项目中快速生成不同版本数据库之间的差异SQL，同时还能够自动将新版中新增表中默认数据一并导入到旧版本中。**

### 1\. 主要功能 ###  
mysql虽然提供了mysqldiff工具，但实际使用中还有些不满足要求的地方，所以用python写了一个。  
*  比对两个数据库的差异；  
*  比对两张表的差异；  
*  支持外键的处理；
*  自动忽略表字段的顺序差异；  
*  支持同步新增表中数据；  
*  将生成的差异sql保存到文件或者自动执行；  
*  记录错误日志，出错时方便排查。

### 2\. 使用方法  
&emsp;&emsp;**mysqldiff.py**用[web.py](http://webpy.org/ "web.py")作为连接数据库的工具，因此在使用之前要确保环境中已经安装web.py模块，如果没有安装，可以使用下面的命令进行安装：  
 ```
 pip install web.py
 ```
**命令格式：**  
```
 python mysqldiff.py [param1] [param2] { [param3]....}
 ```
**参数说明：**  
*  -x  
 自动执行差异SQL语句，默认不执行。
*  -c  
 是否插入新增表中的默认数据  
*  s=[user]:[pass]@[host]:[port]  
 当两个数据库的连接配置相同时可以用该参数，否则用下面的sn和so分别指明。  
     user：用户名  
     pass：密码  
     host：ip地址  
     port：端口  
*  so=[user]:[pass]@[host]:[port]  
 数据库配置。  
*  sn=[user]:[pass]@[host]:[port]  
 被参照的数据库配置。  
*  [db_new]{.[table_name]}:[db_old]{.[table_name]}  
 数据库名.表名，不指名表名时对比整个数据库。  
*  file=[diff_file]  
 差异化sql保存位置，默认保存在diff.sql文件中。  

**示例：**  
 对比db_new和db_old两个数据库中的表结构差异，并将sql语句保存到diff.sql中，同时直接执行sql语句：
 ```
 python mysqldiff.py -x s=comclay:123456@192.168.16.122:3306 db_new:db_old file=diff.sql
 ```
### 3\. 数据库对比 ###  
db_old数据库中只包含user表：  
 ![](https://i.imgur.com/YJfklRk.png)  
db_new数据库中新增了course，并添加了一个外键约束：  
 ![](https://i.imgur.com/Yq2AQa5.png)  
 ![](https://i.imgur.com/Z2uUhiv.png)  
使用下方命令进行差异化对比：  
 ```
 python mysqldiff.py -c s=clear:123456@192.168.18.149:3306 db_new:db_old
 ```
生成的diff.sql如下：  
```sql
/****************************** 关闭外键约束 ******************************/
SET FOREIGN_KEY_CHECKS=0;

/****************************** course ******************************/
CREATE TABLE `course` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `course` varchar(32) COLLATE utf8_unicode_ci DEFAULT NULL,
  `grade` int(11) DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `fk` (`user_id`),
  CONSTRAINT `fk` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE NO ACTION ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

INSERT INTO course (grade, course, user_id, id) VALUES 
	(60, 'english', 1, 1);

/****************************** 开启外键约束 ******************************/
SET FOREIGN_KEY_CHECKS=1;

```
