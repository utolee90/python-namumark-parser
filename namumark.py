import re
import string
import os

from template import *
from processor import Processor

class PlainWikiPage:

    def __init__(self, text, title):
        self.title = title
        self.text = text

    def get_page(self):
        return {
            "title": self.title if self.title else "",
            "text": self.text if self.text else ""
        }


class NamuMark:

    def __init__(self, wiki_text :dict):

        self.list_tag = [
            ['*', 'ul'],
            ['1.', 'ol class="decimal"'],
            ['A.', 'ol class="upper-alpha"'],
            ['a.', 'ol class="lower-alpha"'],
            ['I.', 'ol class="upper-roman"'],
            ['i.', 'ol class="lower-roman"'],
        ]

        self.h_tag = [
            r'(^|\n)======#?\s?(.*)\s?#?======',
            r'(^|\n)=====#?\s?(.*)\s?#?=====',
            r'(^|\n)====#?\s?(.*)\s?#?====',
            r'(^|\n)===#?\s?(.*)\s?#?===',
            r'(^|\n)==#?\s?(.*)\s?#?==',
            r'(^|\n)=#?\s?(.*)\s?#?='
        ]
        self.h_tag_hide = [
            r'(^|\n)======#\s?(.*)\s?#======',
            r'(^|\n)=====#\s?(.*)\s?#=====',
            r'(^|\n)====#\s/(.*)\s?#====',
            r'(^|\n)===#\s?(.*)\s?#===',
            r'(^|\n)==#\s?(.*)\s?#==',
            r'(^|\n)=#\s?(.*)\s?#='
        ]
        self.multi_bracket = {
            "{{{": {
                "open": "{{{",
                "close": "}}}",
                "processor": "render_processor"
            },
            "[": {
                "open": "[",
                "close": "]",
                "processor": "macro_processor"
            }
        }
        self.single_bracket = {
            "=": {
              "open": "=",
              "close": "=",
              "processor" : "header_processor"
            },
            "{{{": {
                "open": "{{{",
                "close": "}}}",
                "processor": "text_processor"
            },
            "[[": {
                "open": "[[",
                "close": "]]",
                "processor": "link_processor"
            },
            "[": {
                "open": "[",
                "close": "]",
                "processor": "macro_processor"
            },
            "~~": {
                "open": "~~",
                "close": "~~",
                "processor": "text_processor"
            },
            "--": {
                "open": "--",
                "close": "--",
                "processor": "text_processor"
            },
            "__": {
                "open": "__",
                "close": "__",
                "processor": "text_processor"
            },
            "^^": {
                "open": "^^",
                "close": "^^",
                "processor": "text_processor"
            },
            ",,": {
                "open": ",,",
                "close": ",,",
                "processor": "text_processor"
            }
        }

        # 문법 사용할 때 만드는 특정문자
        self.IDENTIFIER = ['[', '{', '#', '>', '~', '-', '*', '(', '=']

        # 사용중인 매크로
        self.macros= []
        #  사용중인 매크로 텍스트
        self.macro_texts = []
        # 사용중인 인라인 매크로
        self.inline_macros = []

        # 위키 페이지 - TITLE / TEXT
        self.WIKI_PAGE = wiki_text
        # test 부분만
        self.WIKI_TEXT = wiki_text.get('text')
        # 줄별로 나누어서 처리
        self.WIKI_PAGE_LINES = self.WIKI_TEXT.split('\n')
        self.image_as_link = False
        self.wap_render = False

        # 목록으로
        self.TOC = self.get_toc()
        self.fn = []
        # 분류
        self.category = []
        # 링크 모음
        self.links = []
        self.fn_cnt = 0
        self.prefix = ""
        self.included = False
        self.title_list = []

        # 결과물 - HTML, mw
        self.parsed = ""
        self.mw = ""


        self.MIN_TITLE_INDEX = min(list(filter(lambda x: bool(re.search(self.h_tag[6-x], self.WIKI_TEXT)), range(1,7))))

        self.subtitles = self.title_structure(self.WIKI_TEXT,"")['titles']
        self.parts = self.title_structure(self.WIKI_TEXT,"")['parts']

    # parser for mediawiki -
    @staticmethod
    def pre_parser(text: str):
        # <>태그 왼쪽 괄호 해제
        text = re.sub(r"<(/?[a-zA-Z0-9]*?)>", r"&lt;\1>", text)
        # &;태그 왼쪽 amp 치환
        text= re.sub(r"&([#0-9A-Za-z]*?);", r"&amp;\1;", text)

        return text

    # 템플릿 안에 사용할 때 풀어쓰기
    @staticmethod
    def inner_template(text:str):
        return text.replace('{|', '{{{!}}').replace('|}', '{{!}}}').replace('||', '{{!!}}').replace('|', '{{!}}')

    # 복잡한 배열 - 선형으로 고치기 -> [[a,b,c],[d,[e,f]]]=> [a,b,c,d,e,f]
    @classmethod
    def simplify_array(cls, args):
        res = []
        for elem in args:
            if "list" not in str(type(elem)):
                res.append(elem)
            else:
                res.extend(cls.simplify_array(elem))
        return res

    # 문단 위치-> 이름 찾기 -> 정수열로...
    def find_paragraph_by_index(self, *args):
        res = self.subtitles.copy()
        try:
            i =0
            while i<len(args):
                res = res[args[i]]
                i +=1
            if "list" in str(type(res)):
                return res[0]
            else: return res
        except:
            return ''

    # 링크 모으기
    def get_links(self):
        if not self.WIKI_PAGE.title:
            return []
        if len(self.links) == 0:
            self.parsed = self.pre_parser(self.WIKI_PAGE['text'])
            self.parsed = self.mw_scan(self.parsed)

        return self.links

    # 파싱하기
    def parse_HTML(self):
        if not self.WIKI_PAGE.title:
            return ""
        self.parsed = self.pre_parser(self.WIKI_PAGE['text'])
        self.parsed = self.to_HTML(self.parsed)
        return self.parsed

    # HTML 바꾸기
    def to_HTML(self, text:str):
        res = ""

        # 넘겨주기 형식 - 빈문서로 처리
        if re.fullmatch(r"#(?:redirect|넘겨주기) (.+)", text, flags=re.I):
            return ""

        # 정의중입니다.


    # 미디어위키 스캔
    def mw_scan(self, text: str):
        # 결과
        result = ""
        # 텍스트를 줄 단위로 나누기
        strlines = text.split('\n')
        # 파서
        macros = []
        parsed_texts = []
        # 한 줄 파서 목록
        inline_macros = []

        #넘겨주기 형식 - 빠르게 처리
        if re.fullmatch(r"#(?:redirect|넘겨주기) (.+)", text, flags=re.I):
            target = re.fullmatch(r"#(?:redirect|넘겨주기) (.+)", text, flags=re.I)
            target_link = target.group(1).split('#')[0] # # 기호 뒷부분은 넘겨주기한 문서 정보를 알 수 없으므로 무시한다.
            self.links = [{"target": target_link, "type": "redirect"}]
            return "#redirect [[{0}]]".format(target_link)

        # 줄 단위로 패턴 검색
        idx = 0
        while idx < len(strlines):
            cur_line = strlines[idx]



    # 헤딩 구조로 문서 나누어 분석하기. structure
    def title_structure(self, text:str, title=""):
        # 기초 타이틀
        titles = [title]
        parts = [text]

        for idx in range(1,7):
            res_part = self.title_structure_part(text, idx)
            # idx 단계의 파트가 없을 때는 계속
            if len(res_part['titles'])==1:
                # 마지막 단계에서도 파트가 없음 - 결과 출력
                if idx == 6:
                    return {"titles": titles, "parts": parts}
                else:
                    continue
            # idx 단계의 파트가 있을 때 그 단계에서 쪼개고 마무리
            else:
                titles.extend(res_part['titles'][1:])
                parts = res_part['parts']
                break

        # titles/parts 리스트를 기준으로 반복 실행
        for idx in range(len(titles)):
            res_part = self.title_structure(parts[idx], titles[idx])
            if len(res_part['titles'])>1:
                titles[idx] = res_part['titles']
                parts[idx] = res_part['parts']

        self.subtitles = titles
        self.parts = parts

        return {"titles": titles, "parts": parts}

    def title_structure_part(self, text:str, level: int):
        parts = []
        titles  = ['']
        # 문단별로 나누기
        tmp = 0
        paragraph_pattern = self.h_tag[6 - level]
        title_patterns = re.finditer(paragraph_pattern, text)
        for pat in title_patterns:
            starting = pat.start()
            titles.append(pat.group(0))
            parts.append(text[tmp:starting-1]) if starting>0 else parts.append("")
            tmp = pat.end()+1
        # 마지막 문단 패턴 뒤 추가
        parts.append(text[tmp:])
        return {"titles":titles, "parts": parts}

    # 복잡한 리스트 -> 딕셔너리 형태로 정리
    # ['일번', ['이번','삼번']] => {'0': '일번', '1': '이번', '1.1':'삼번'}
    @classmethod
    def unravel_list(cls, args):
        res = {}
        for (idx,elem) in enumerate(args):
            if 'list' not in str(type(elem)):
                res[str(idx)] = elem
            else:
                res_0 = cls.unravel_list(elem)
                for (key,val) in res_0.items():
                    res[f"{idx}.{key}"] = val
        return res

    #목차 찾기
    def get_toc(self):
        res = []
        subtitles = self.subtitles
        unraveled = self.unravel_list(subtitles)

        for (key,val) in unraveled.items():
            # subtitle에서 헤딩 문법 제외하고 글자만 추출
            val_0 = re.search(r"=#? (.*?) #?=", val).group(1)
            if key == "0":
                continue
            elif key[-4:] == ".0.0":
                res.append(f"{key[:-4]}. {val_0}")
            elif key[-2:] == ".0":
                res.append(f"{key[:-2]}. {val_0}")
            else:
                res.append(f"{key}. {val_0}")

        return res

    # 헤드라인용 처리
    def header_processor(self, text:str):
        # 숨김 패턴이 있는지 확인
        res = text
        # 이전 문단이 숨김 패턴이 있는지 확인
        if 'hiding_header' in self.macros:
            res = "{{숨김 끝}}\n"+res
            self.macros.remove('hiding_header')

        if re.search(r'(=+#) .*? (#=+)', res):
            res = re.sub(r'(=+)# (.*?) #(=+)', r'\1 \2 \3\n{{숨김 시작}}', res)
            self.macros.append('hiding_header')
        
        return res

    # 중괄호 여러줄 프로세싱. 기본적으로 문법 기호 포함.
    # 멀티라인일 때는 type = multi
    def render_processor(self, text: str, type: str):
        res = ""
        render_stack = [] # render_processor 안에 여러 기호가 있을 때
        # 여러 줄 표시. 즉 줄이 닫히지 않았을 때
        if type == "multi":
            # html - 내부 내용 그대로 출력
            if text[0:10].lower() == "{{{#!html ":
                self.macros.append('html')
                return text[10:]

            # wiki -> div tag로 감싸서 처리. 단 display:inline이 있을 때는 span 태그로 처리
            elif text[0:10].lower() == "{{{#!wiki ":
                # 첫줄 부분만 남겨서
                text_head = text.split('\n')[0][10:]
                is_inline = "display:inline" in text_head
                text_head_len = len(text_head)+1
                text_remain = text[text_head_len:-3]
                if is_inline:
                    return f"<span {text_head}>{self.mw_scan(self.pre_parser(text_remain))}</span>"
                else:
                    return f"<div {text_head}>\n{self.mw_scan(self.pre_parser(text_remain))}\n</div>"

            # 전용 태그: span/inline -> span tag로 감싸서 처리.
            elif text[0:10].lower() == "{{{#!span " or text[0:12].lower() == "{{{#!inline":
                # 첫줄 부분만 남겨서
                text_head = text.split('\n')[0][10:]
                text_head_len = len(text_head) + 1
                text_remain = text[text_head_len:-3]
                return f"<span {text_head}>{self.mw_scan(self.pre_parser(text_remain))}</span>"


            # folding -> 숨김 시작 틀 사용
            elif text[0:13].lower() == "{{{#!folding ":
                # 첫줄 부분 분리
                text_head = text.split('\n')[0][10:]
                text_head_len = len(text_head)+1
                text_remain = text[text_head_len:-3]
                return f"{{{{숨김 시작|title={self.inner_template(text_head)}}}}}\n{self.mw_scan(self.pre_parser(text_remain))}\n{{{{숨김 끝}}}}"

            #syntax/source -> syntaxhighlight
            elif text[0:12].lower() in ["{{{#!syntax ", "{{{#!source "]:
                text_head = text.split('\n')[0][10:]
                text_head_len = len(text_head)+1
                text_remain = text[text_head_len:-3]
                return f"<syntaxhighlight lang={text_head}>\n{text_remain}\n</syntaxhighlight>"

            # poem -> poem,
            elif text[0:10].lower() == "{{{#!poem ":
                # 첫줄 부분 분리
                text_head = text.split('\n')[0][10:]
                text_head_len = len(text_head)+1
                text_remain = text[text_head_len:-3]
                return f"<poem style={text_head}>\n{self.mw_scan(self.pre_parser(text_remain))}\n</poem>"

            # math -> math
            elif text[0:10].lower() == "{{{#!math ":
                # math 태그는 첫줄부터 사용
                text_remain = text[10:-3]
                return f"<math>{text_remain}</math>"

            # code -> code
            elif text[0:10].lower() == "{{{#!code ":
                # code 태그는 첫줄부터 사용
                text_remain = text[10:-3]
                return f"<code>{self.mw_scan(self.pre_parser(text_remain))}</code>"

            #나머지 #!패턴-> 중괄호 뒷부분 모두 pre태그로 처리
            elif text[0:5] == "{{{#!":
                text_remain = text[4:-3]
                self.macros.append('pre')
                return f"<pre>{text_remain}</pre>"

            # #color 패턴 -> 색상처리
            elif re.match(r"\{\{\{(#[0-9A-Za-z]+ )", text):
                text_head = re.match('\{\{\{(#[0-9A-Za-z]+) ', text).group(0)
                text_remain = text[len(text_head):]
                color = re.match('\{\{\{(#[0-9A-Za-z]+)', text).group(1)
                if not re.match(r'#[0-9A-Fa-f]{3} ',color) and not re.match(r'#[0-9A-Fa-f]{6} ',color):
                    # 색상명 있으면 색상코드로 변경해서 처리. 커스텀 색상 추가용
                    if color[1:] in WEB_COLOR_LIST.keys():
                        color = '#'+WEB_COLOR_LIST[color[1:]]
                    # 나머지
                    else:
                        return f"<div>{text_head[4:]}{self.mw_scan(self.pre_parser(text_remain))}"

                return f"<div style='{color}'>{self.mw_scan(self.pre_parser(text_remain))}</div>"

            # #color,#color 패턴 -> 라이트/다크모드.
            # 리브레 위키에서는 mw.loader.load('//librewiki.net/index.php?title=사용자:Utolee90/liberty.js&action=raw&ctype=text/javascript') 삽입시에만 유효
            elif re.match(r"\{\{\{(#[0-9A-Za-z]+,#[0-9A-Za-z] )", text):
                colors = re.match('\{\{\{(#[0-9A-Za-z]+),(#[0-9A-Za-z]+) ', text)
                text_head = colors.group(0)
                text_remain = text[len(text_head):]
                color1, color2 = colors.group(1), colors.group(2)


    # 리스트 파싱
    def list_parser(self, text:str, offset:int):
        list_table = []
        strlen = len(text)
        line_start = offset

        stop_func = False

        for i in range(offset, strlen):
            pass







