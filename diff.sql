/*************************************关闭外键约束*************************************/
SET FOREIGN_KEY_CHECKS=0;

/*************************************表或列重命名*************************************/
ALTER TABLE `course_old` RENAME TO `course`;

ALTER TABLE `user` CHANGE `name` `username`;

ALTER TABLE `user` RENAME TO `user_new`;

/**************************************新增表***************************************/
CREATE TABLE `user_course` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `course_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `fk_uc_1` (`user_id`),
  KEY `fk_uc_2` (`course_id`),
  CONSTRAINT `fk_uc_1` FOREIGN KEY (`user_id`) REFERENCES `user_new` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_uc_2` FOREIGN KEY (`course_id`) REFERENCES `course` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

/**********************************往新增表中导入旧表中数据**********************************/
INSERT INTO user_course (course_id,user_id) VALUES 
	(1, 1);

/***************************************修改***************************************/
ALTER TABLE course 
	DROP COLUMN `user_id`;

/*************************************开启外键约束*************************************/
SET FOREIGN_KEY_CHECKS=1;

