create database netops;

use netops;
drop table IF EXISTS users;
create table users(
username varchar(40) COLLATE utf8_bin NOT NULL COMMENT '???',
identify varchar(64) COLLATE utf8_bin NOT NULL COMMENT '??hash?API key',
subname varchar(40) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '???',
phone varchar(20) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '??',
mail varchar(50) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '??',
rid varchar(40) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '??ID',
update_time varchar(10) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '??????',
last_login varchar(10) COLLATE utf8_bin NOT NULL  DEFAULT '' COMMENT '??????',
primary key(username)
);

drop table IF EXISTS roles;
create table roles(
rid varchar(40) COLLATE utf8_bin NOT NULL COMMENT '??ID',
name varchar(40) COLLATE utf8_bin NOT NULL COMMENT '???',
descr varchar(64) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '????',
primary key(rid)
);

drop table IF EXISTS role_pages;
create table role_pages(
rid varchar(40) COLLATE utf8_bin NOT NULL COMMENT '??ID',
page_id bigint COLLATE utf8_bin NOT NULL COMMENT '??ID',
privilege varchar(1) COLLATE utf8_bin NOT NULL DEFAULT '0'  COMMENT '???? 0 ?? 1??',
primary key(rid, page_id)
);

drop table IF EXISTS pages;
create table pages(
page_id bigint COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '?????ID',
name varchar(40) COLLATE utf8_bin NOT NULL COMMENT '????',
classify varchar(40) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '????',
sort_num varchar(10) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '????',
path varchar(100) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '??',
p_type varchar(1) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '??0or??1',
descr varchar(300) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '????',
hide varchar(1) COLLATE utf8_bin NOT NULL DEFAULT '0' COMMENT '0????????',
parent_id bigint COLLATE utf8_bin NOT NULL DEFAULT 0 COMMENT '??',
icon varchar(40) COLLATE utf8_bin NOT NULL COMMENT '??',
primary key(page_id)
);

drop table IF EXISTS pages_uri;
create table pages_uri(
uri_id bigint COLLATE utf8_bin NOT NULL AUTO_INCREMENT COMMENT '????ID',
page_id bigint COLLATE utf8_bin NOT NULL COMMENT '??ID',
uri varchar(60) COLLATE utf8_bin NOT NULL COMMENT '????',
descr varchar(64) COLLATE utf8_bin NOT NULL DEFAULT '' COMMENT '????',
privilege varchar(1) COLLATE utf8_bin NOT NULL DEFAULT '0'  COMMENT '???? 0 ?? 1??',
primary key(uri_id)