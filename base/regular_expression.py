# encoding=utf-8

'''
正则表达式
w s d b + . * ? ^ $ () [] {} | \
[]用来指定一个字符集
[012]
[0-9]
[^0-9]
[a-zA-Z0-9]
^用来指定开头
$用来指定结尾
\w 相当于[a-zA-Z0-9]
\W 相当于[^a-zA-Z0-9]
\s 匹配任何空白字符
\S 匹配任何非空白字符
\d 相当于[0-9]
\D 相当于[^0-9]
\b 匹配一个单词  如 r‘\bhello\b’ 精确匹配'hello'，将不会匹配'helloworld', 但是会匹配'hello world'
{} 表示前面字符重复的次数,{n}表示重复n次{n,m}表示重复n-m次，{n,}表示n次或更多次
* 表示前面字符重复0次或以上
+ 表示前面字符重复1次或以上
? 表示前面字符重复0次或1次(即前面符号可有可无)。另外一个作用就是放在重复的后面表示非贪婪模式
  如 p = r'ab*?' 与r'ab*'的区别就是后者是贪婪模式，前者是非贪婪模式。前者匹配ab，后者匹配abbbbbb（尽可能匹配更多的b）
(pattern1|pattern2) 小括号与或来起到分组的作用.

正则表达式的编译
如果正则表达式经常使用，为了更快的速度，所以讲正则表达式先编译，这样比解释更快
re.compile()
如 p = r'\d{3,4}-?\d{8}'
p_tel = re.compile(p)
p_tel.findall('010-12345678')

re.compile(p,re.I)  //re.I是指不区分字母大小写，在compile的时候可以加这样的属性，更加灵活

re.match()  //从开头位置匹配 m = re.match(pattern,string) , m.group() 得到匹配的结果
re.search()  //从各个位置查找匹配  m = re.search(pattern,string),  m.group() 得到匹配的结果
re.sub() //替换substitute  re.sub(pattern,replacement,string)直接返回sub后的结果，str类型
re.split() //分割 re.split(pattern,string)直接返回split后的结果，list类型
re.findall() //查询 re.findall(pattern, string)直接返回find后的结果，list类型

一些flag
re.I //忽略大小写
re.M //要匹配的字符串是多行的doc string
re.X //定义的正则是多行的doc string

正则分组
(pattern1|pattern2) 小括号与或来起到分组的作用. 分组的另一个作用是控制返回的值
如
s = 'hello name=guang yes hello name=kevin yes'
p1= r'hello name=\w+ yes'
p2= r'hello name=(\w+) yes'
re.findall(p1,s) //返回的是['hello name=guang yes', 'hello name=kevin yes']
re.findall(p2,s) //返回的是['guang', 'kevin']
这就是小括号分组的另一个作用
'''
