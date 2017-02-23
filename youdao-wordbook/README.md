## 有道词典单词本xml文件生成器

### 使用
```
usage: wordbook_xml_generator.py [-h] -d DIR [-x XML] [-f FILE]

generate xml for youdao dict wordbook.

optional arguments:
  -h, --help            show this help message and exit
  -d DIR, --dir DIR     /path/to/wordbook/dir
  -x XML, --xml XML     /path/to/xml/file
  -f FILE, --file FILE  wordbook filename, whose path is relatived to <dir>.
                        If ignored, all wordbook files in wordbook dir will be
                        used to generate xml.
```

### 单词本组织
1. wordbook为单词本目录，所有单词文件都在此目录下
2. 每个单词文件以该文件中的单词来自的博客或者论文命名
3. 所有单词文件格式都遵循下面的格式：其中phonetic是可选字段
```
<word>\t<translation>\t<phonetic>

awk 'NF == 0{printf "%s\n",word;word="";next}{if(length(word)==0){word=$0}else{word=word" "$0}}
```

### xml文件生成规则
1. 单词文件名会添加到xml的<trans>字段中，看单词表时可以知道这个单词在那几篇文章中出现过
2. 如果两个单词文件中都包含了某个单词，并且两个文件都参与生成xml，那么<trans>采用追加策略
3. 有道词典xml文件格式（版本：7.0.1.0214）
```xml
<wordbook>
    <item>
        <word>apple</word>
        <trans><![CDATA[n. 苹果，苹果树，苹果似的东西；[美俚]炸弹，手榴弹，（棒球的）球；[美俚]人，家伙。]]></trans>
        <phonetic><![CDATA[['æpl]]]></phonetic>
        <tags></tags>
        <progress>-1</progress>
    </item>
    <item>
        <word>apple</word>
        <trans><![CDATA[n. 苹果，苹果树，苹果似的东西；[美俚]炸弹，手榴弹，（棒球的）球；[美俚]人，家伙。]]></trans>
        <phonetic><![CDATA[['æpl]]]></phonetic>
        <tags></tags>
        <progress>-1</progress>
    </item>
<wordbook>
```