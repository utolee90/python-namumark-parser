import re
import string
import os

from template import WEB_COLOR_LIST, *
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

        self.subtitles = self.title_structure(self.WIKI_TEXT,"")['titles']
        self.parts = self.title_structure(self.WIKI_TEXT,"")['parts']

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
    def parse_mw(self):
        if not self.WIKI_PAGE.title:
            return ""
        # self.parsed = self.pre_parser(self.WIKI_PAGE['text'])
        self.parsed = self.mw_scan(self.WIKI_PAGE['text'])
        return self.parsed

    # HTML 바꾸기
    def to_mw(self, text:str):
        res = ""

        # 넘겨주기 형식 - 빈문서로 처리
        if re.fullmatch(r"#(?:redirect|넘겨주기) (.+)", text, flags=re.I):
            return ""

        # 정의중입니다.

    # 미디어위키 스캔
    # def to_mw(self, text:str):
    #     res = ""
    #
    #     # 넘겨주기 형식 - 빈문서로 처리
    #     if re.fullmatch(r"#(?:redirect|넘겨주기) (.+)", text, flags=re.I):
    #         return ""
    #
    #     # 정의중입니다.


    # 미디어위키 메인함수
    '''미디어위키 메인함수 - 텍스트 - 파싱하는 함수
    파싱 전략
    1. 나무마크로된 텍스트를 각 줄로 나누기
    2. 각 줄에 위키 패턴에 따라 매크로 지정. 윗줄과 패턴이 동일하면 패턴 텍스트에 삽입.
    2.1. 패턴 종류 : none(아무것도 없음), pre(문법없음), list(목록), math(수식), syntax(문법강조), html(생 HTML), bq(블록), table(테이블)
    2.2. 패턴은 중복해서 서술할 수 있음.
    3. 각 줄의 입력을 보고 패턴 파악하기
    3.1. 패턴이 동일할 경우 pattern_result 변수에 내용 추가
    3.2. 다음 줄의 패턴이 달라질 경우 patter_result 결과를 정의한 후 pattern에 따른 프로세서를 이용해서 파싱된 내용 추가
    '''
    def mw_scan(self, text: str):
        # 결과
        result = ""
        # 파서 하나 적용할 결과
        parser_result = ""
        # 텍스트를 줄 단위로 나누기
        strlines = text.split('\n')
        # 파서
        macros = ['none']
        self.macros = macros
        parsed_texts = []

        #넘겨주기 형식 - 빠르게 처리
        if re.fullmatch(r"#(?:redirect|넘겨주기) (.+)", text, flags=re.I):
            target = re.fullmatch(r"#(?:redirect|넘겨주기) (.+)", text, flags=re.I)
            target_link = target.group(1).split('#')[0] # # 기호 뒷부분은 넘겨주기한 문서 정보를 알 수 없으므로 무시한다.
            self.links = [{"target": target_link, "type": "redirect"}]
            return "#redirect [[{0}]]".format(target_link)

        # 줄 단위로 패턴 검색후 파서 적용하기
        idx = 0
        while idx < len(strlines):
            cur_line = strlines[idx]
            if self.get_pattern(cur_line) == "hr":
                result += "<hr />\n"
            elif self.get_pattern(cur_line) == "comment":
                cont = re.match("^##(.*)", cur_line).group(1)
                result += f"<!--{cont}-->\n"

            # 매크로가 동일할 때 - list, bq, table, none
            elif macros[-1] == self.get_pattern(cur_line):
                parser_result += cur_line

            # 매크로가 달라질 때
            else:
                if macros[-1] == 'list':
                    # 리스트 파서 추가
                    result += self.list_parser(parser_result)
                elif macros[-1] == 'bq':
                    # 블록 파서 결과 추가
                    result += self.bq_parser(parser_result)
                elif macros[-1] == 'table':
                    #표 파서 결과 추가
                    result += self.table_parser(parser_result)
                else:
                    # 파서 결과 추가
                    result += self.render_processor(parser_result, 'multi')

                parser_result = ""
                macros[-1] = self.get_pattern(cur_line)
                self.macros = macros

            idx +=1

    # 패턴 분석 함수 - 텍스트 통해서 패턴 분석
    def get_pattern(self, text:str):
        # 목록 형태
        if re.match(r"^\s{1,6}(\*|1\.|A\.|a\.|I\.|i\.)", text):
            return 'list'
        # 블록 인용문
        elif re.match(r"^>", text):
            return 'bq'
        # 표
        elif re.match(r"^\|\|", text):
            return 'table'
        # 주석
        elif re.match(r"^##", text):
            return 'comment'
        # 가로선
        elif text[0:4] == "----":
            return 'hr'
        # 아무것도 없을 때
        else:
            return 'none'


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

        if re.search(r'(=+#)\s?.*?\s?(#=+)', res):
            res = re.sub(r'(=+)#\s?(.*?)\s?#(=+)', r'\1 \2 \3\n{{숨김 시작}}', res)
            self.macros.append('hiding_header')
        
        return res

    # 중괄호 여러줄 프로세싱. 기본적으로 문법 기호 포함.
    # 멀티라인일 때는 type = multi
    def render_processor(self, text: str, type: str=""):
        r = 0
        res = ""

        parsing_symbol_multiline = ['{', '[', '\n']
        render_stack = [] # render_processor 안에 여러 기호가 있을 때
        # 여러 줄 표시. 즉 줄이 닫히지 않았을 때
        if type == "multi":
            # 임시로 파싱하기 전 코드 저장
            temp_preparsed = ""

            # 낱자마다 찾기
            while r < len(text):
                # 낱자별로 검색
                letter = text[r]

                if letter in parsing_symbol_multiline:

                    # html - 내부 내용 그대로 출력
                    if text[r:r+10].lower() == "{{{#!html ":
                        # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                        res += self.render_processor(temp_preparsed) if temp_preparsed != "" else ""
                        text_remain = text[r+10:]
                        closed_position = text_remain.find("}}}")
                        parsed = text_remain[:closed_position] if closed_position>=0 else text_remain
                        r += 13 + len(parsed) if parsed_find("}}}")>=0 else 10+len(parsed)
                        res += parsed
                        temp_preparsed = ""

                    # wiki -> div tag로 감싸서 처리. 단 display:inline이 있을 때는 span 태그로 처리
                    elif text[r:r+10].lower() == "{{{#!wiki ":
                        # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                        res += self.render_processor(temp_preparsed) if temp_preparsed != "" else ""
                        # 첫줄 부분만 남겨서
                        text_head = text[r:].split('\n')[0][10:]
                        is_inline = "display:inline" in text_head
                        text_head_len = len(text_head)+1
                        text_remain = text[r+text_head_len:]

                        open_count = text_remain.count("{{{")
                        tmppos = 0
                        tmpcnt = 0
                        while tmpcnt <= open_count and tmppos >= 0:
                            tmppos = text_remain.find("}}}", tmppos + 1)
                            tmpcnt += 1
                        if tmppos >= 0:
                            text_remain = text_remain[:tmppos]

                        if is_inline:
                            res += f"<span {text_head}>{self.mw_scan(self.pre_parser(text_remain))}</span>"
                        else:
                            res += f"<div {text_head}>\n{self.mw_scan(self.pre_parser(text_remain))}\n</div>"
                        temp_preparsed = ""

                    # folding -> 숨김 시작 틀 사용
                    elif text[0:13].lower() == "{{{#!folding ":
                        # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                        res += self.render_processor(temp_preparsed) if temp_preparsed != "" else ""
                        # 첫줄 부분 분리
                        text_head = text.split('\n')[0][10:]
                        text_head_len = len(text_head)+1
                        text_remain = text[text_head_len:]

                        open_count = text_remain.count("{{{")
                        tmppos = 0
                        tmpcnt = 0
                        while tmpcnt <= open_count and tmppos >= 0:
                            tmppos = text_remain.find("}}}", tmppos + 1)
                            tmpcnt += 1
                        if tmppos >= 0:
                            text_remain = text_remain[:tmppos]

                        r += 16+ len(text_remain) if tmppos >=0 else 13+len(text_remain)

                        res += f"{{{{숨김 시작|title={self.inner_template(text_head)}}}}}\n{self.mw_scan(self.pre_parser(text_remain))}\n{{{{숨김 끝}}}}"
                        temp_preparsed = ""

                    #syntax/source -> syntaxhighlight
                    elif text[0:12].lower() in ["{{{#!syntax ", "{{{#!source "]:
                        # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                        res += self.render_processor(temp_preparsed) if temp_preparsed != "" else ""
                        parsed = re.match(r"\{\{\{#!(syntax|source) (.*?)}}}", text[r:], re.MULTILINE).group(1)
                        r += 15 + len(parsed)
                        text_head = parsed.split('\n')[0]
                        text_head_len = len(text_head)+1
                        text_remain = text[text_head_len:]
                        res += f"<syntaxhighlight lang=\"{text_head}\">\n{text_remain}\n</syntaxhighlight>"
                        temp_preparsed = ""

                    # 색깔 표현
                    elif letter == "{" and re.match(r"^\{\{\{#(.*?) (.*?)", text[r:], re.MULTILINE):
                        # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                        res += self.render_processor(temp_preparsed) if temp_preparsed != "" else ""
                        color = re.match(r"\{\{\{#(.*?) (.*)", text[r:], re.MULTILINE).group(1)
                        pre_parsed = re.match(r"\{\{\{#(.*?) (.*)", text[r:], re.MULTILINE).group(2)
                        # pre_parsed에서 {{{ 기호와 }}} 기호 갯수를 센다.
                        pre_parsed_open_count = pre_parsed.count("{{{")
                        tmppos = 0
                        tmpcnt = 0

                        # pre_parsed_open_count+1번째 "}}}" 찾기
                        while tmpcnt <= pre_parsed_open_count and tmppos >= 0:
                            tmppos = pre_parsed.find("}}}", tmppos + 1)
                            tmpcnt += 1
                        if tmppos >= 0:
                            parsed = pre_parsed[:tmppos]
                        else:
                            parsed = pre_parsed

                        r += 8 + len(color) + len(parsed) if tmppos >= 0 else 5 + len(color) + len(parsed)  # r값 늘리기
                        if re.match(r"[0-9A-Fa-f]{6}", color):
                            res += f"{{{{색|#{color}|{self.render_processor(self.pre_parser(parsed))}}}}}"
                        elif re.match(r"[0-9A-Fa-f]{3}", color):
                            res += f"{{{{색|#{color}|{self.render_processor(self.pre_parser(parsed))}}}}}"
                        elif color in WEB_COLOR_LIST.keys():
                            res += f"{{{{색|#{WEB_COLOR_LIST[color]}|{self.render_processor(self.pre_parser(parsed))}}}}}"
                        else:  # 일단은 <pre>로 처리
                            res += f"<pre>#{color} {parsed}</pre>"
                        temp_preparsed = ""

                    # 글씨 키우기/줄이기
                    elif letter == "{" and re.match(r"\{\{\{(+|-)([1-5]) (.*)", text[r:]):
                        # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                        res += self.render_processor(temp_preparsed) if temp_preparsed != "" else ""
                        sizer = re.match(r"\{\{\{(+|-)([1-5]) (.*)", text[r:], re.MULTILINE).group(1)
                        num = int(re.match(r"\{\{\{(+|-)([1-5]) (.*)", text[r:], re.MULTILINE).group(2))
                        pre_parsed = re.match(r"\{\{\{(+|-)([1-5]) (.*)", text[r:], re.MULTILINE).group(3)
                        # pre_parsed에서 {{{ 기호와 }}} 기호 갯수를 센다.
                        pre_parsed_open_count = pre_parsed.count("{{{")
                        tmppos = 0
                        tmpcnt = 0

                        while tmpcnt <= pre_parsed_open_count and tmppos >= 0:
                            tmppos = pre_parsed.find("}}}", tmppos + 1)
                            tmpcnt += 1
                        if tmppos >= 0:
                            parsed = pre_parsed[:tmppos]
                        else:
                            parsed = pre_parsed

                        r += 9 + len(parsed) if temppos >= 0 else 6 + len(parsed)
                        base = self.render_processor(self.pre_parser(parsed))
                        for _ in range(num):
                            base = "<big>" + base + "</big>" if sizer == "+" else "<small>" + base + "</small>"
                        res += base
                        temp_preparsed = ""

                    # # #color,#color 패턴 -> 라이트/다크모드.
                    # # 리브레 위키에서는 mw.loader.load('//librewiki.net/index.php?title=사용자:Utolee90/liberty.js&action=raw&ctype=text/javascript') 삽입시에만 유효
                    # elif re.match(r"\{\{\{(#[0-9A-Za-z]+,#[0-9A-Za-z] )", text):
                    #     colors = re.match('\{\{\{(#[0-9A-Za-z]+),(#[0-9A-Za-z]+) ', text)
                    #     text_head = colors.group(0)
                    #     text_remain = text[len(text_head):]
                    #     color1, color2 = colors.group(1), colors.group(2)

                    # 나머지 - pre로 처리하기
                    elif text[0:3] == "{{{":
                        # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                        res += self.render_processor(temp_preparsed) if temp_preparsed != "" else ""
                        text_remain = text[r + 3:]
                        closed_position = text_remain.find("}}}")
                        parsed = text_remain[:closed_position] if closed_position >= 0 else text_remain
                        r += 6 + len(parsed) if parsed_find("}}}") >= 0 else 3 + len(parsed)
                        res += "<pre>"+parsed+"</pre>"
                        temp_preparsed = ""

                    # 나중에 처리...
                    elif text[0:6] == "[math(":
                        # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                        res += self.render_processor(temp_preparsed) if temp_preparsed != "" else ""

                    # 개행기호 - 앞부분의 내용을 전부 파싱...
                    elif letter == "\n":
                        # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                        res += self.render_processor(temp_preparsed) if temp_preparsed != "" else ""
                        if re.match(r"^\n{2,}", text[r:], re.MULTILINE):
                            crlines = re.match(r"^\n{2,}", text[r:], re.MULTILINE).group(0)
                            res +=crlines # 2행 이상 개행시에는 똑같이 개행
                            r += len(crlines)
                            temp_preparsed = ""
                        elif text[r+1] != "\n": #한줄 개행이면 <br/>기호 삽입.
                            res +="<br />"
                            r += 1
                            temp_preparsed = ""
                    # 나머지 케이스
                    else:
                        temp_preparsed +=letter
                        r +=1
                # 나머지 케이스
                else:
                    temp_preparsed += letter
                    r += 1

            return res

        else: # 멀티라인이 아닐 때 파싱

            # 낱말별로 검사
            while r < len(text):
                letter = text[r]
                parsing_symbol = ['{', "[", '~', '-', '_', '^', ',', "<"]

                if letter in parsing_symbol:

                    # 문법 무시
                    if letter == "{" and re.match(r"^\{\{\{([^#].*?)}}}", text[r:]):
                    parsed = re.match(r"\{\{\{([^#].*?)}}}", text[r:]).group(1)
                    r += 6 + len(parsed)
                    res += f"<nowiki>{parsed}</nowiki>"

                    # 색깔 표현
                    elif letter == "{" and re.match(r"^\{\{\{#(.*?) (.*?)", text[r:]):
                        color = re.match(r"\{\{\{#(.*?) (.*)", text[r:]).group(1)
                        pre_parsed = re.match(r"\{\{\{#(.*?) (.*)", text[r:]).group(2)
                        # pre_parsed에서 {{{ 기호와 }}} 기호 갯수를 센다.
                        pre_parsed_open_count = pre_parsed.count("{{{")
                        tmppos = 0
                        tmpcnt = 0

                        # pre_parsed_open_count+1번째 "}}}" 찾기
                        while tmpcnt <= pre_parsed_open_count and tmppos >= 0:
                            tmppos = pre_parsed.find("}}}", tmppos + 1)
                            tmpcnt += 1
                        if tmppos >= 0:
                            parsed = pre_parsed[:tmppos]
                        else:
                            parsed = pre_parsed

                        r += 8 + len(color) + len(parsed) if tmppos >=0 else 5+len(color)+len(parsed)  # r값 늘리기
                        if re.match(r"[0-9A-Fa-f]{6}", color):
                            res += f"{{{{색|#{color}|{self.render_processor(self.pre_parser(parsed))}}}}}"
                        elif re.match(r"[0-9A-Fa-f]{3}", color):
                            res += f"{{{{색|#{color}|{self.render_processor(self.pre_parser(parsed))}}}}}"
                        elif color in WEB_COLOR_LIST.keys():
                            res += f"{{{{색|#{WEB_COLOR_LIST[color]}|{self.render_processor(self.pre_parser(parsed))}}}}}"
                        else:  # 일단은 <nowiki>로 처리
                            res += f"<nowiki>#{color} {parsed}</nowiki>"

                    # 글씨 키우기/줄이기
                    elif letter == "{" and re.match(r"\{\{\{(+|-)([1-5]) (.*)", text[r:]):
                        sizer = re.match(r"\{\{\{(+|-)([1-5]) (.*)", text[r:]).group(1)
                        num = int(re.match(r"\{\{\{(+|-)([1-5]) (.*)", text[r:]).group(2))
                        pre_parsed = re.match(r"\{\{\{(+|-)([1-5]) (.*)", text[r:]).group(3)
                        # pre_parsed에서 {{{ 기호와 }}} 기호 갯수를 센다.
                        pre_parsed_open_count = pre_parsed.count("{{{")
                        tmppos = 0
                        tmpcnt = 0

                        while tmpcnt <= pre_parsed_open_count and tmppos >= 0:
                            tmppos = pre_parsed.find("}}}", tmppos + 1)
                            tmpcnt += 1
                        if tmppos >= 0:
                            parsed = pre_parsed[:tmppos]
                        else:
                            parsed = pre_parsed

                        r += 9 + len(parsed) if temppos>=0 else 6+len(parsed)
                        base = self.render_processor(self.pre_parser(parsed))
                        for _ in range(num):
                            base = "<big>" + base + "</big>" if sizer == "+" else "<small>" + base + "</small>"
                        res += base

                    # 각주. 각주 내 각주 기호가 있을 경우 오류가 생길 수 있으므로 나중에 별도의 함수를 이용해서 해결할 예정.
                    elif letter == "[" and re.match(r"\[\*(.*?) (.*?)]", text[r:]):
                        refname = re.match(r"\[\*(.*?) (.*?)]", text[r:]).group(1)
                        refcont = re.match(r"\[\*(.*?) (.*?)]", text[r:]).group(2)
                        r += 4 + len(refname) + len(refcont)
                        if refname == "":
                            res += f"<ref>{self.render_processor(self.pre_parser(refcont))}</ref>"
                        else:
                            res + + f"<ref name=\"{refname}\">{self.render_processor(self.pre_parser(refcont))}</ref>"

                    # 링크 처리 - 외부링크, 내부링크 공통처리
                    elif letter == "[" and re.match(r"\[\[(.*?)]]", text[r:]):
                        article = re.match(r"\[\[(.*?)(\|.*?)?]]", text[r:]).group(1)
                        cont = re.match(r"\[\[(.*?)(\|.*?)?]]", text[r:]).group(2)[1:] #앞의 |기호는 빼고 파싱해야 함.
                        r += len(re.match(r"\[\[(.*?)]]", text[r:]).group(0))
                        res += self.link_processor(article, cont)

                    # 매크로
                    elif letter == "[" and re.match(r"\[([^\[*].*?)]", text[r:]):
                        cont = re.match(r"\[(.*?)\]", text[r:]).group(1)
                        r += 2 + len(cont)
                        res += self.simple_macro_processor(cont)

                    # 취소선1
                    elif letter == "~" and re.match(r"~~(.*?)~~", text[r:]):
                        cont = re.match(r"~~(.*?)~~", text[r:]).group(1)
                        r += 4 + len(cont)
                        res += f"<del>{self.render_processor(self.pre_parser(cont))}</del>"

                    # 취소선2
                    elif letter == "-" and re.match(r"--(.*?)--", text[r:]):
                        cont = re.match(r"--(.*?)--", text[r:]).group(1)
                        r += 4 + len(cont)
                        res += f"<del>{self.render_processor(self.pre_parser(cont))}</del>"

                    # 밑줄
                    elif letter == "_" and re.match(r"__(.*?)__", text[r:]):
                        cont = re.match(r"__(.*?)__", text[r:]).group(1)
                        r += 4 + len(cont)
                        res += f"<u>{self.render_processor(self.pre_parser(cont))}</u>"

                    # 위 첨자
                    elif letter == "^" and re.match(r"\^\^(.*?)\^\^", text[r:]):
                        cont = re.match(r"\^\^(.*?)\^\^", text[r:]).group(1)
                        r += 4 + len(cont)
                        res += f"<sup>{self.render_processor(self.pre_parser(cont))}</sup>"

                    # 아래첨자
                    elif letter == "," and re.match(r",,(.*?),,", text[r:]):
                        cont = re.match(r",,(.*?)^^", text[r:]).group(1)
                        r += 4 + len(cont)
                        res += f"<sub>{self.render_processor(self.pre_parser(cont))}</sub>"

                    # 수식 <math> 태그 - 동일하게 해석
                    elif letter == "<" and re.match(r"^<math>(.*?)</math>", text[r:]):
                        cont = re.match(r"^<math>(.*?)</math>", text[r:]).group(0)
                        r += len(cont)
                        res += cont

                    # 나머지
                    else:
                        res += letter
                        r += 1
                # 나머지 문자들 - 문법에서 사용되지 않으므로 처리하지 않음.
                else:
                    res += letter
                    r += 1

            return res


    # 리스트 파싱
    # text는 공백 포함 목록형 나무마크 문법, offset은 공백 갯수
    # function for list_parser
    def list_parser(self, text: str):
        list_table = []
        open_tag_list = []
        lines = text.split('\n')
        res = ''

        # 파싱 준비
        for list_line in lines:
            # 공백 갯수
            res_line = self.list_line_parser(list_line)
            list_table.append(res_line)

        # 레벨 숫자
        lvl = 0
        tgn = ''
        tgn_total = ""

        # 우선 ul과 ol class="decimal"로만 구성되어 있을 때는 심플하게 파싱하기
        list_table_kinds = set(map(lambda x: x['type'], list_table))

        if list_table_kinds.issubset({'ul', 'ol class="decimal"'}):
            for tbl in list_table:
                # 레벨 숫자가 tbl보다 작을 때
                if lvl< tbl['level']:
                    diff = tbl['level'] - lvl
                    tgn_total = tgn_total+"*"*diff if tbl['type'] == "ul" else tgn_total+"#"*diff
                    lvl = tbl['level']
                    tgn = tbl['type']
                    res += tgn_total + self.render_processor(tbl['preparsed']) + "\n"

                # 레벨 숫자가 앞의 숫자와 동일
                elif lvl == tbl['level'] and tgn == tbl['type']:
                    res += tgn_total + self.render_processor(tbl['preparsed']) + "\n"

                # 레벨 숫자가 앞의 숫자와 동일, 다른 타입
                elif lvl == tbl['level'] and tgn != tbl['type']:
                    tgn_total = tgn_total[:-1]+"*" if tbl['type'] == "ul" else tgn_total[:-1]+"#"
                    tgn = tbl['type']
                    res += tgn_total + self.render_processor(tbl['preparsed']) + "\n"

                # 레벨 숫자가 앞의 숫자보다 작음,
                elif lvl > tbl['level']:
                    # 우선 기호부터 확인해보자
                    tgn_total_level = tgn_total[tbl['level']-1] # 해당 단계에서 심볼부터 확인

                    #레벨 기준으로 확인
                    if (tgn_total_level == "*" and tbl['type'] == 'ul') or (tgn_total_level == "#" and tbl['type'] == 'ol class="decimal"'):
                        # 그냥 컷을 함.
                        tgn_total = tgn_total[:tbl['level']]
                    else:
                        tgn_total = tgn_total[:tbl['level']-1]+"*" if tbl['type'] == 'ul' else tgn_total[:tbl['level']-1]+"#"

                    lvl = tbl['level']
                    tgn = tbl['type']
                    res += tgn_total + self.render_processor(tbl['preparsed']) + "\n"

        else:
            for tbl in list_table:
                # 같은 레벨, 같은 태그명
                if lvl == tbl['level'] and tgn == tbl['type']:
                    res += f"<li>{self.render_processor(tbl['preparsed'])}</li>\n"
                # 같은 레벨, 태그명만 다를 때
                elif lvl == tbl['level'] and tgn != tbl['type']:
                    # 태그 닫기
                    res += f"</{tgn[0:2]}>\n"
                    tgn = tbl['type']
                    open_tag_list[-1] = tgn
                    res += f"<{tbl['type']}>\n"
                    res += f"<li>{self.render_processor(tbl['preparsed'])}</li>\n"
                # 레벨값보다 수준이 더 클 때
                elif lvl + 1 == tbl['level']:
                    res += f"<{tbl['type']}>\n"
                    res += f"<li>{self.render_processor(tbl['preparsed'])}</li>\n"
                    lvl = tbl['level']
                    tgn = tbl['type']
                    open_tag_list.append(tbl['type'])
                # 레벨값보다 수준이 더 작을 때
                elif lvl > tbl['level']:
                    for tn in open_tag_list[:tbl['level'] - 1:-1]:
                        res += f"</{tn[0:2]}>\n"

                    open_tag_list = open_tag_list[0:tbl['level']]
                    lvl = tbl['level']

                    if open_tag_list[-1] == tbl['type']:
                        res += f"<li>{self.render_processor(tbl['preparsed'])}</li>\n"
                        tgn = tbl['type']
                    else:
                        res += f"</{open_tag_list[-1][0:2]}>\n"
                        res += f"<{tbl['type']}>\n"
                        res += f"<li>{self.render_processor(tbl['preparsed'])}</li>\n"
                        tgn = tbl['type']

            # 마지막으로 남아있으면...
            for tgx in open_tag_list[::-1]:
                res += f"</{tgx[0:2]}>\n"

        return res

    # 리스트 한줄 파싱,
    # 결과 : {type: (유형), preparsed: (li 태그 안에 파싱된 텍스트), level: (레벨)}
    def list_line_parser(self, text: str):
        res = {}
        # 공백 갯수
        spacing = len(re.match(r"^(\s{1,5})", text).group(1))
        res['level'] = spacing
        if text[spacing] == "*":
            res['type'] = 'ul'
            res['preparsed'] = text[spacing + 1:]
        else:
            for tg in self.list_tag[1:]:
                if text[spacing:spacing + 2] == tg[0]:
                    res['type'] = tg[1]
                    res['preparsed'] = text[spacing + 2:]
                    break
        return res
    
    # 한 줄짜리 [매크로] 형식의 함수 처리하기
    @staticmethod
    def simple_macro_processor(text:str):
        
        const_macro_list = {
            "br": "<br />",
            "date": "{{#timel:Y-m-d H:i:sP}}",
            "datetime": "{{#timel:Y-m-d H:i:sP}}",
            "목차": "__TOC__",  # 일단 표시. 그러나 목차 길이가 충분히 길면 지울 생각
                  "tableofcontents": "__TOC__",
                                     "각주": "{{각주}}",
            "footnote": "{{각주}}",
            "clearfix": "{{-}}",
            "pagecount": "{{NUMBEROFPAGES}}",
            "pagecount(문서)": "{{NUMBEROFARTICLES}}",
        }
        # 단순 텍스트일 때
        if text in const_macro_list.keys():
            return const_macro_list[text]

        # 만 나이 표시
        elif re.match(r"age\(\d\d\d\d-\d\d-\d\d\)", text):
            yr = re.match(r"age\((\d\d\d\d)-(\d\d)-(\d\d)\)", text).group(1)
            mn = re.match(r"age\((\d\d\d\d)-(\d\d)-(\d\d)\)", text).group(2)
            dy = re.match(r"age\((\d\d\d\d)-(\d\d)-(\d\d)\)", text).group(3)
            return f"{{{{#expr: {{{{현재년}}}} - {yr} - ({{{{현재월}}}} <= {mn} and {{{{현재일}}}} < {dy})}}}}"

        # 잔여일수/경과일수 표시
        elif re.match(r"dday\(\d\d\d\d-\d\d-\d\d\)", text):
            yr = re.match(r"dday\((\d\d\d\d)-(\d\d)-(\d\d)\)", text).group(1)
            mn = re.match(r"dday\((\d\d\d\d)-(\d\d)-(\d\d)\)", text).group(2)
            dy = re.match(r"dday\((\d\d\d\d)-(\d\d)-(\d\d)\)", text).group(3)
            return f"{{{{#ifexpr:{{{{#time:U|now}}}} - {{{{#time:U|{yr}-{mn}-{dy}}}}}>0|+}}}}{{{{#expr:floor (({{{{#time:U|now}}}} - {{{{#time:U|{yr}-{mn}-{dy}}}}})/86400)}}}}"
        # 수식 기호
        elif re.match(r"math\((.*)\)", text):
            tex = re.match(r"math\((.*)\)", text).group(1)
            return f"<math>{tex}</math>"
            # 앵커 기호
            elif re.match(r"anchor\((.*)\)", text):
            aname = re.match(r"anchor\((.*)\)", text).group(1)
            return f"<span id='{aname}></span>"

        # 루비 문자 매크로
        elif re.match(r"ruby\((.*)\)", text):
            cont = re.match(r"ruby\((.*?)(,ruby=.*?)?(,color=.*?)?\)").group(1)
            ruby_part = re.match(r"ruby\((.*?)(,ruby=.*?)?(,color=.*?)?\)").group(2)
            color_part = re.match(r"ruby\((.*?)(,ruby=.*?)?(,color=.*?)?\)").group(3)
            if ruby_part != "":
                ruby = ruby_part[6:]
                if color_part != "":
                    color = color_part[7:]
                    return f"<ruby><rb>{cont}</rb><rp>(</rp><rt style=\"color:{color}\">{ruby}</rt><rp>)</rp>"
                else:
                    return f"<ruby><rb>{cont}</rb><rp>(</rp><rt>{ruby}</rt><rp>)</rp>"

        # 틀 포함 문구
        elif re.match(r"include\((.*)\)", text):
            conts = re.match(r"include\((.*)\)", text).group(1)
            conts_list = conts.split(',')  # 안의 내용 - 틀:틀이름,변수1=값1,변수2=값2,
            transcluding = conts_list[0].strip()  # 문서 목록
            res = f"{{{{{transcluding}"
            # 내부에 변수 없을 때
            if len(conts_list) == 1:
                return res + "}}"
            # 내부에 변수가 있을 때
            else:
                for vars in conts_list[1:]:
                    res += "|" + vars
                return res + "}}"

        else:
            return ""

    # 한 줄짜리 링크형태 문법 처리
    def link_processor(self, link, text):
        # 외부 링크
        if re.match(r"https?://(.*)", link):
            return f"{link}" if text == "" else f"[{link} {self.render_processor(text, '')}]"
        # 문단기호 링크에 대비
        elif re.match(r"$(.*?)#s\-(.*)", link):
            article = re.match(r"$(.*?)#s\-(.*)", link).group(1)
            paragraph = re.match(r"$(.*?)#s\-(.*)", link).group(2)
            paragraph_list = paragraph.split(".")
            paragraph_name = self.find_paragraph_by_index(paragraph_list)
            return f"[[{article}#{paragraph_name}]]" if text == "" else f"[[{article}#{paragraph_name}|{self.render_processor(text, '')}]]"

        else:
            return f"[[{link}]]" if text == "" else f"[[{link}|{self.render_processor(text)}]]"

    # 표 파싱 함수
    # 인자: text -> 나무마크 문서 데이터 중 표 부분만 따온 부분 텍스트(주의: 전체 문서 텍스트를 넣지 말 것!)
    # TODO: 정규표현식 최적화, 셀 내부 꾸미기 기능 구현
    def convert_to_mw_table(text:str):
        # [br] -> <br>로 바꾸기
        while re.search(r"\[br\]", text) and re.search(r"\[br\]", text).start() != -1:
            matchstart = re.search(r"\[br\]", text).start()
            matchend = re.search(r"\[br\]",text).end()
            text = text[0:matchstart] + "<br>" + text[matchend:]
        # 엔터키 개행은 \n 문자를 하나 더 추가
        regex_2 = re.compile(r"([^\n\|]+)\n([^\n\|]+)")
        if regex_2.search(text):
            substrings = regex_2.search(text).groups()
            first = regex_2.search(text).start()
            lastend = regex_2.search(text).end()
            lastword = text[lastend+1:]
            text = text[0:first]
            for substring in substrings:
                text = text + substring + "\n\n"
            text = text + lastword
        print(text)
        print("----------")
        # 셀 병합 및 '{| class="wikitable", '|+' |', '|-', '|}'등의 기호로 변형 : 최종 작업 단계
        result = "{| class=\"wikitable\" "
        rowmergingcell = 0
        RowMergingCellNum = 0
        Firstchar = True
        while (re.match(r"\|", text)):
            if (re.match(r"\|([^\|\n]+)\|", text)):
                result += "\n|+ " + text[re.match(r"\|([^\|\n]+)\|", text).start()+1:re.match(r"\|([^\|\n]+)\|", text).end()-1]
                text = "||" + text[re.match(r"\|([^\|\n]+)\|", text).end():]
            elif (re.match(r"\|\|([\|]+)(\<\|[0-9]+\>)?([^\n]+)(\|\|\n)?", text)): # 여러 개의 | 문자로 가로 병합하는 경우 또는 세로 병합을 위한 더미 셀 추가
                if RowMergingCellNum > 0: # 더미 셀이 필요함
                    for i in range(0, RowMergingCellNum):
                        result += "\n| style=\"display:none\" | "
                    RowMergingCellNum = 0
                elif re.search(r"\|\|([\|]+)\<\|[0-9]+\>([^\|]+)", text): # 가로 -> 세로 병합
                    rowmergingcell = (re.match(r"\|\|([\|]+)",text).end() - re.match(r"\|\|([\|]+)",text).start()) // 2
                    result += "\n| colspan=\""+ str(rowmergingcell) + "\" rowspan=\""+ text[re.search(r"\<\|[0-9]+\>", text).start()+2:re.search(r"\<\|[0-9]+\>",text).end()-1] +"\" | "
                    result += text[re.search(r"<\|([0-9]+)\>", text).end():re.search(r"<\|([0-9]+)\>([^\|]+)", text).end()]
                    rowmergingcell = 0
                else: # 가로 병합
                    rowmergingcell = (re.match(r"\|\|([\|]+)",text).end() - re.match(r"\|\|([\|]+)",text).start()) // 2
                    result += "\n| colspan=\""+ str(rowmergingcell) + "\" | "
                    rowmergingcell = 0
                    result += text[re.match(r"\|\|([\|]+)", text).end():re.match(r"\|\|([\|]+)([^\|\n]+)", text).end()]
                text = text[re.match(r"\|\|([\|]+)(\<\|[0-9]+\>)*([^\|\n]+)",text).end():]
                if (text == ""):
                    result += "\n|}"
            elif re.match(r"\|\|([\|]+)\n", text): # 가로 병합 때 버려질 셀들을 처리
                rowmergingcell = (re.match(r"\|\|([\|]+)",text).end() - re.match(r"\|\|([\|]+)",text).start()) // 2
                for i in range(0, rowmergingcell+1):
                    if i == 0:
                        result += "\n| style=\"display:none\" | "
                rowmergingcell = 0
                result += "\n|-"
                text = text[re.match(r"\|\|([\|])+\n", text).end():]
                if (text == ""):
                    result += "\n|}"
            elif re.match(r"\|\|\<\|[0-9]+\>(\<\-[0-9]+\>|\|\|([\|]*))",text):
                # col - row merge
                if Firstchar:
                    result += "\n| "
                    Firstchar = False
                else:
                    result += "|| "
                # now put in the spanning part
                result += "rowspan=\"" + text[re.search(r"\<\|([0-9]+)\>", text).start()+2:re.search(r"\<\|([0-9]+)\>",text).end()-1] + "\" "
                if re.search(r"\|\|([\|]+)", text[2:]):
                    rowmergingcell += (re.match(r"\|\|([\|]+)", text[2:]).end() - re.match(r"\|\|([\|]+)", text[2:]).start() ) // 2
                    result += "colspan=\"" + str(rowmergingcell) + "\" | "
                    RowMergingCellNum += rowmergingcell
                    rowmergingcell = 0
                else:
                    result += "colspan=\"" + text[re.search(r"\<\-[0-9]+\>", text).start()+2:re.search(r"\<\-[0-9]+\>",text).end()-1] + "\" | "
                # put in the context
                result += text[re.search(r"\<\-[0-9]+\>",text).end():re.search(r"\<\-[0-9]+\>[^\|]+",text).end()] + " |" + text[re.search(r"\<\-[0-9]+\>",text).end():re.search(r"\<\-[0-9]+\>[^\|]+",text).end()] + " |"
                text = text[re.search(r"\<\-[0-9]+\>[^\|]+",text).end():]
            elif re.match(r"\|\|(<\-[0-9]+\>|[\|]+)\<\|[0-9]+\>",text):
                # row - col merge
                if Firstchar:
                    result += "\n| "
                    Firstchar = False
                else:
                    result += "|| "
                # now put in the spanning part
                if re.search(r"\|\|([\|]+)",text):
                    rowmergingcell += (re.match(r"\|\|([\|]+)", text).end() - re.match(r"\|\|([\|]+)", text).start() ) // 2
                    result += "colspan=\"" + str(rowmergingcell) + "\" "
                    rowmergingcell = 0
                else:
                    result += "colspan=\"" + text[re.search(r"\<\-([0-9]+)\>", text).start()+2:re.search(r"\<\-([0-9]+)\>",text).end()-1] + "\" "
                # put in the context with row spanning part
                result += "rowspan=\"" + text[re.search(r"\<\|[0-9]+\>", text).start()+2:re.search(r"\<\|[0-9]+\>",text).end()-1] + "\" | " + text[re.search(r"\<\|[0-9]+\>",text).end():re.search(r"\<\|[0-9]+\>[^\|]+",text).end()]
                text = text[re.search(r"\<\|[0-9]+\>[^\|]+",text).end():]
            elif re.match(r"\|\|\<\|[0-9]+\>",text): # 세로 병합 기호 단독
                if Firstchar:
                    result += "\n| "
                    Firstchar = False
                else:
                    result += "|| "
                result += "rowspan=\"" + text[re.match(r"\|\|\<\|[0-9]+\>", text).start()+4:re.match(r"\|\|\<\|[0-9]+\>",text).end()-1] + "\" | " + text[re.match(r"\|\|\<\|[0-9]+\>",text).end():re.match(r"\|\|\<\|[0-9]+\>[^\|]+",text).end()]
                text = text[re.match(r"\|\|\<\|[0-9]+\>([^\|]+)",text).end():]
            elif re.match(r"\|\|\<\-[0-9]+\>",text): # 가로 병합 기호 단독
                if Firstchar:
                    result += "\n| "
                    Firstchar = False
                else:
                    result += "|| "
                result += "colspan=\"" + text[re.match(r"\|\|\<\-[0-9]+\>", text).start()+4:re.match(r"\|\|\<\-[0-9]+\>",text).end()-1] + "\" | " + text[re.match(r"\|\|\<\-[0-9]+\>",text).end():re.match(r"\|\|\<\-[0-9]+\>[^\|]+",text).end()]
                text = text[re.match(r"\|\|\<\-[0-9]+\>[^\|]+",text).end():]
            elif re.match(r"\|\|([^\|\n]+)",text): # 평범한 셀 내용
                result += "\n" + text[re.match(r"\|\|([^\|\n]+)",text).start()+1:re.match(r"\|\|([^\|\n]+)",text).end()]
                text = text[re.match(r"\|\|([^\|\n]+)",text).end():]
            elif (re.match(r"\|\|\n", text)): # 개행
                result += "\n| style=\"display:none\" |  \n|-"
                Firstchar = True
                text = text[re.match(r"\|\|\n",text).end():]
                if (text == ""):
                    result += "|}"
            elif (re.match(r"\|\|",text)):
                result += "\n|}"
                text = text[2:]
            # print(text) # debug
        # 도로 text에 파싱된 결과를 삽입
        text = result
        # 최종 확인
        # print(text)
        return text



