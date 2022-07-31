import re

from template import WEB_COLOR_LIST


class PlainWikiPage:

    def __init__(self, text, title):
        self.title = title
        self.text = text

    def get_page(self):
        return {
            "title": self.title if self.title else "",
            "text": self.text if self.text else ""
        }


# 나무마크 상수 정의 함수
class NamuMarkConstant:
    # ul, ol 리스트용 태그
    LIST_TAG = [
        ['*', 'ul'],
        ['1.', 'ol class="decimal"'],
        ['A.', 'ol class="upper-alpha"'],
        ['a.', 'ol class="lower-alpha"'],
        ['I.', 'ol class="upper-roman"'],
        ['i.', 'ol class="lower-roman"'],
    ]
    # 문단 제목용 태그
    H_TAG = [
        r'(^|\n)======([^=].*)======\s*(\n|$)',
        r'(^|\n)=====([^=].*)=====\s*(\n|$)',
        r'(^|\n)====([^=].*)====\s*(\n|$)',
        r'(^|\n)===([^=].*)===\s*(\n|$)',
        r'(^|\n)==([^=].*)==\s*(\n|$)',
        r'(^|\n)=([^=].*)=\s*(\n|$)'
    ]

    # 파서 태그
    RENDER_PROCESSOR_PARSER = [
        '{{{!#html ',
        '{{{!#wiki ',
        '{{{!#folding ',
        '{{{!#syntax ',
        '{{{!#source ',
        '{{{#',
        '{{{+',
        '{{{',
        '[math(',
        '\n'
    ]

    # 나무마크에서 <, &기호를 문법 표시로 치환하기. 미디어위키에서 예상치 못한 태그 사용을 방지하기 위한 조치
    @staticmethod
    def pre_parser(text: str):
        # <>태그 왼쪽 괄호 해제
        text = re.sub(r"<(/?[a-zA-Z0-9]*?)>", r"&lt;\1>", text)
        # &;태그 왼쪽 amp 치환
        text = re.sub(r"&([#0-9A-Za-z]*?);", r"&amp;\1;", text)

        return text

    # 미디어위키에서 템플릿 안에 내용의 문자를 집어넣을 때 내용 치환
    @staticmethod
    def inner_template(text: str):
        return text.replace('{|', '{{{!}}').replace('|}', '{{!}}}').replace('||', '{{!!}}').replace('|', '{{!}}')

    # 다단 리스트 - 풀어써서 1단 리스트로 고치기 [[a,b,c],[d,[e,f]]]=> [a,b,c,d,e,f]
    @classmethod
    def simplify_array(cls, args):
        res = []
        for elem in args:
            if "list" not in str(type(elem)):
                res.append(elem)
            else:
                res.extend(cls.simplify_array(elem))
        return res

    # 복잡한 리스트 -> 딕셔너리 형태로 정리
    # ['일번', ['이번','삼번']] => {'0': '일번', '1': '이번', '1.1':'삼번'}
    @classmethod
    def unravel_list(cls, args):
        res = {}
        for (idx, elem) in enumerate(args):
            if 'list' not in str(type(elem)):
                res[str(idx)] = elem
            else:
                res_0 = cls.unravel_list(elem)
                for (key, val) in res_0.items():
                    res[f"{idx}.{key}"] = val
        return res


class NamuMark(NamuMarkConstant):

    # dict 형태 : {"title": (문서 제목), "text": (위키 문법)}
    def __init__(self, wiki_text: dict):

        # 제목 숨김 여부 - 문단 숨김 여부 확인하기 위해 사용.
        self.hiding_header = False
        #  사용중인 매크로 텍스트
        self.macro_texts = []

        # 위키 페이지 - TITLE / TEXT
        self.WIKI_PAGE = wiki_text
        # test 부분만
        self.WIKI_TEXT = wiki_text.get('text')
        # 줄 단위 나누기
        self.WIKI_TEXT_LINES = self.WIKI_TEXT.split('\n')

        self.image_as_link = False
        self.wap_render = False

        self.subtitles = self.title_structure(self.WIKI_TEXT, "")['titles']
        self.parts = self.title_structure(self.WIKI_TEXT, "")['parts']

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
        self.line_idx = 0

        if re.search(r"(^|\n)=+.*=+", self.WIKI_TEXT):
            self.MIN_TITLE_INDEX = min(
                list(filter(lambda x: bool(re.search(self.H_TAG[6 - x], self.WIKI_TEXT)), range(1, 7))))

    # 문단 위치-> 이름 찾기 -> 정수열로...
    def find_paragraph_by_index(self, *args):
        res = self.subtitles.copy()
        try:
            i = 0
            while i < len(args):
                res = res[args[i]]
                i += 1
            if "list" in str(type(res)):
                return res[0]
            else:
                return res
        except:
            return ''

    # 링크 모으기
    def get_links(self):
        if not self.WIKI_PAGE['title']:
            return []
        if len(self.links) == 0:
            self.parsed = self.WIKI_PAGE['text']
            self.parsed = self.to_mw(self.parsed)

        return self.links

    # 한줄 텍스트 패턴 분석 함수 - 앞에 있는 표시를 이용해서
    @staticmethod
    def get_pattern(text: str):
        # 헤더
        if re.match(r"^={1,6}.*?={1,6}", text):
            return 'header'
        # 목록 형태
        elif re.match(r"^\s{1,6}(\*|1\.|A\.|a\.|I\.|i\.)", text):
            return 'list'
        # 블록 인용문
        elif re.match(r"^>", text):
            return 'bq'
        # 표
        elif re.match(r"^\|", text):
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

    # 파싱하기 - to_mw 함수 호출
    def parse_mw(self):
        if not self.WIKI_PAGE['title']:
            return ""
        # self.parsed = self.WIKI_PAGE['text']
        self.parsed = self.to_mw(self.WIKI_PAGE['text'])
        return self.parsed

    # HTML 바꾸기
    def to_html(self, text: str):
        res = ""

        # 넘겨주기 형식 - 빈문서로 처리
        if re.fullmatch(r"#(?:redirect|넘겨주기) (.+)", text, flags=re.I):
            return ""

        # 정의중입니다.

    # 매크로 맵 - 텍스트를 줄 단위로 나눈 뒤 [줄, 매크로, 매크로 종료여부] 파트로 출력
    def macro_map(self, text: str):
        # 한줄 -> [한줄, 매크로명, 매크로 분기점여부]
        txt_lines = text.split('\n')  # 글을 출력하기
        res = []
        table_open = False  # 열린 표가 있는지 확인
        for (idx, line) in enumerate(txt_lines):
            # 테이블이 열렸는지 확인해보자
            if self.get_pattern(line) == 'table' and line.strip()[-2:] != "||":
                table_open = True

            if table_open:  # 테이블이 열려있으면 패턴은 무조건 테이블로. 계속 검색
                res.append([line+'\n', 'table', False])
            else:
                # 가로선/헤더이거나 마지막 줄에서는 무조건 True
                macro_cut = True if idx == len(txt_lines) - 1 or self.get_pattern(line) in ['header', "hr"] \
                    else self.get_pattern(line) != self.get_pattern(txt_lines[idx + 1])
                res.append([line+'\n', self.get_pattern(line), macro_cut])

            # table_open이 닫히는 조건 - 마지막 줄이 ||로 끝난다. 그러면 res
            if table_open and (line.strip()[-2:] == "||" or idx == len(txt_lines) - 1):
                table_open = False
                # 마지막으로 추가한 res의 분기점여부도 변경
                res[-1][2] = len(txt_lines) - 1 == idx or self.get_pattern(line) != self.get_pattern(txt_lines[idx + 1])

        return res

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

    def to_mw(self, text: str, part=False):
        # 결과
        result = ""
        # 파서 하나 적용할 결과
        parser_result = ""
        # 텍스트를 줄 단위로 나눈 뒤 매크로 맵을 산출
        macros = self.macro_map(text)
        if not part:
            self.line_idx = 0

        # 넘겨주기 형식 - 간단하게 처리할 수 있음.
        if re.fullmatch(r"#(?:redirect|넘겨주기) (.+)", text, flags=re.I):
            target = re.fullmatch(r"#(?:redirect|넘겨주기) (.+)", text, flags=re.I)
            target_link = target.group(1).split('#')[0]  # # 기호 뒷부분은 넘겨주기한 문서 정보를 알 수 없으므로 무시한다.
            self.links = [{"target": target_link, "type": "redirect"}]
            return "#redirect [[{0}]]".format(target_link)

        # 개행기호 단위로 파싱한 후에 표시
        line_idx = 0  # 첫 줄
        while line_idx < len(macros):  # 마지막 줄까지 검색
            cur_line = macros[line_idx][0]  # 현재 줄 표시
            cur_macro = macros[line_idx][1]  # 현재 줄 매크로 값
            macro_cut = macros[line_idx][2]  # 매크로 분기 여부

            if macro_cut:
                parser_result += cur_line  # 파서 결과 더하기
                # 가로선 또는 주석 - misc_processor
                if cur_macro == "hr" or cur_macro == "comment":
                    result += self.misc_processor(parser_result)
                # 문단 제목 - header_processor
                elif cur_macro == "header":
                    result += self.header_processor(parser_result)
                # 목록 형태
                elif cur_macro == "list":
                    result += self.list_parser(parser_result)
                # 블록문
                elif cur_macro == "bq":
                    result += self.bq_parser(parser_result)
                # 표
                elif cur_macro == "table":
                    result += self.table_parser(parser_result)
                # 나머지
                else:
                    result += self.render_processor(parser_result)

                parser_result = ""  # 파서 결과는 다시 비우기

            else:
                # 매크로 컷이 아니면 그냥 parser_result에 더하기
                parser_result += cur_line

            line_idx += 1
            if not part:
                self.line_idx = line_idx

        if not part:
            self.line_idx = 0

        return result[:-1]

    # 헤딩 구조로 문서 나누어 분석하기. structure
    def title_structure(self, text: str, title=""):
        # 기초 타이틀
        titles = [title]
        parts = [text]

        for idx in range(1, 7):
            res_part = self.title_structure_part(text, idx)
            # idx 단계의 파트가 없을 때는 계속
            if len(res_part['titles']) == 1:
                # 마지막 단계에서도 파트가 없음 - 결과 출력
                if idx == 6:
                    return {"titles": titles, "parts": parts}

            # idx 단계의 파트가 있을 때 그 단계에서 쪼개고 마무리
            else:
                titles.extend(res_part['titles'][1:])
                parts = res_part['parts']
                break

        # titles/parts 리스트를 기준으로 반복 실행
        for idx in range(len(titles)):
            res_part = self.title_structure(parts[idx], titles[idx])
            if len(res_part['titles']) > 1:
                titles[idx] = res_part['titles']
                parts[idx] = res_part['parts']

        self.subtitles = titles
        self.parts = parts

        return {"titles": titles, "parts": parts}

    # 헤딩 구조 문서 나누기 부분
    def title_structure_part(self, text: str, level: int):
        parts = []
        titles = ['']
        # 문단별로 나누기
        tmp = 0
        paragraph_pattern = self.H_TAG[6 - level]
        title_patterns = re.finditer(paragraph_pattern, text)
        for pat in title_patterns:
            starting = pat.start()  # 시작 위치. 개행기호 \n  위치
            ending = pat.end() - 1 if pat.end() < len(text) else pat.end()  # 끝 위치. 개행기호 \n 위치 혹은 마지막.
            titles.append(pat.group(0).replace('\n', ''))  # 개행기호는 제외
            parts.append(text[tmp + 1:starting + 1] if starting > 0 else "")  # 문단기호 앞 개행기호까지 포함
            tmp = ending  # 문단기호 뒤 개행기호 위치로 지정
        # 마지막 문단 패턴 뒤 추가
        parts.append(text[tmp:])
        return {"titles": titles, "parts": parts}

    # 목차 찾기
    def get_toc(self):
        res = []
        subtitles = self.subtitles
        unraveled = self.unravel_list(subtitles)

        for (key, val) in unraveled.items():
            # subtitle에서 헤딩 문법 제외하고 글자만 추출
            if re.match(r"#?\s*(.*?)\s*#?=", val):  # 목차 형태로 찾을 수 있을 때만 값을 추가하자.
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
    def header_processor(self, text: str):
        # 우선 나무위키와 미디어위키의 헤딩 기호는 동일하므로 같은 결과 출력
        res = text

        # 이전 문단이 숨김 패턴이 있는지 확인
        if self.hiding_header:
            res = "{{숨김 끝}}\n" + res
            self.hiding_header = False  # 값 초기화

        # 숨김 문단 패턴 기호가 있는지 확인
        if re.search(r'(=+#)\s?.*?\s?(#=+)', res):
            res = re.sub(r'(=+)#\s?(.*?)\s?#(=+)', r'\1 \2 \3\n{{숨김 시작}}', res)
            self.hiding_header = True

        return res+'\n'

    # 주석, 가로선 처리
    # 패턴 : ---- 또는 ## 주석
    def misc_processor(self, text: str):
        # 가로선 처리
        if re.match(r"^----", text):
            return "<hr/>\n"
        # 주석 처리
        elif re.match(r"^##", text):
            res = "<!--"
            text_split = text.split('\n')
            for line in text_split:
                line_part = re.match(r"^##(.*)", line).group(1)
                res += line_part + '\n'
            # 마지막 \n 기호는 지우고 주석 닫기 처리
            res = res[:-1] + '-->\n'
            return res

    # 중괄호 여러줄 프로세싱. 기본적으로 문법 기호 포함.
    # 멀티라인일 때는 type = multi
    def render_processor(self, text: str):
        r = 0

        parsing_symbol = ['{', "[", '}', ']', '~', '-', '_', '^', ',', "<", '\n']
        # 임시로 파싱하기 전 코드 저장
        temp_preparsed = ""
        part_res = []  # render_stack이 비어있지 않을 때 채운다. 여러 번 여닫는 것에 대응하기 위핸 조건
        render_type = []  # part_res의 각 원소에 대응하는 타입. 만약 parsed 되면 parsed로 바뀐다.
        render_stack = []

        # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
        def render_stack_macro():
            if len(render_stack) == 0:
                part_res.append(self.render_processor(temp_preparsed))
                render_type.append('parsed')
            else:
                part_res.append(temp_preparsed)
                render_type.append(render_stack[-1])

        # 낱자마다 찾기
        while r < len(text):
            # 낱자별로 검색
            letter = text[r]

            if letter in parsing_symbol:

                # html - 내부 내용 그대로 출력
                if text[r:r + 10].lower() == "{{{#!html ":
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    # 타입 지정
                    render_stack.append('html')
                    # 태그 앞당겨서 r값 올린다.
                    temp_preparsed = text[r:r + 10].lower()
                    r += 10

                # wiki -> div tag로 감싸서 처리. 단 display:inline이 있을 때는 span 태그로 처리
                elif text[r:r + 10].lower() == "{{{#!wiki ":
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    render_stack.append("wiki")  # 파싱 타입은 있음
                    # 태그 앞당겨서 r값 올린다.
                    temp_preparsed = text[r:r + 10].lower()
                    r += 10

                # folding -> 숨김 시작 틀 사용
                elif text[r:r + 13].lower() == "{{{#!folding ":
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    render_stack.append("folding")  # 파싱 타입은 있음
                    # 태그 앞당겨서 r값 올린다.
                    temp_preparsed = text[r:r + 13].lower()
                    r += 13

                # syntax/source -> syntaxhighlight
                elif text[r:r + 12].lower() in ["{{{#!syntax ", "{{{#!source "]:
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    render_stack.append("syntax")  # 파싱 타입은 있음
                    # 태그 앞당겨서 r값 올린다.
                    temp_preparsed = text[r:r + 12].lower()
                    r += 12

                # 색깔 표현
                elif letter == "{" and re.match(r"{{{#([A-Za-z0-9,]+?)\s", text[r:], re.MULTILINE):
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    render_stack.append("color")
                    temp_preparsed = re.match(r"{{{#([A-Za-z0-9,]+?)\s", text[r:]).group()
                    r += re.match(r"{{{#([A-Za-z0-9,]+?)\s", text[r:]).end()

                # 글씨 키우기/줄이기
                elif letter == "{" and re.match(r"{{{[+\-]([1-5])\s", text[r:]):
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    render_stack.append("size")
                    temp_preparsed = re.match(r"{{{[+\-]([1-5])\s", text[r:]).group()
                    r += re.match(r"{{{[+\-]([1-5])\s", text[r:]).end()

                # 나머지 { - pre로 처리하기
                elif text[r:r + 3] == "{{{":
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    # pre는 바로 닫기 괄호를 찾은 뒤 parsed로 처리할 수 있다.
                    text_remain = text[r + 3:]
                    closed_position = text_remain.find("}}}")  # 닫기 괄호 위치
                    parsed = text_remain[:closed_position] if closed_position >= 0 else text_remain

                    r += 6 + len(parsed) if parsed.find("}}}") >= 0 else 3 + len(parsed)
                    part_res.append("<pre>" + parsed + "</pre>")  # parsed
                    render_type.append("parsed")  # render_type
                    temp_preparsed = ""

                # 괄호 닫기
                elif text[r:r + 3] == "}}}":
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    if len(render_stack) == 0:
                        part_res.append(self.render_processor(temp_preparsed+"}}}"))
                        render_type.append('parsed')
                        temp_preparsed = ""
                        r += 3

                    # 파싱 타입에 따라 정리 - html이면 있는 그대로 출력
                    elif render_stack[-1] == "html":
                        # 역순 추적
                        for idx, pattern in enumerate(part_res[::-1]):
                            # html은 타입만 parsed로 바꾸고 내용을 바꾸지 않는다.
                            if render_type[-1 - idx] == 'html' and (
                                    idx == len(part_res) - 1 or render_type[-2 - idx] == 'parsed'):
                                render_type[-1 - idx] = 'parsed'
                            elif render_type[-1 - idx] == 'parsed':
                                continue
                            else:
                                break
                        temp_preparsed = ""
                        r += 3
                        render_stack.pop()  # 스택 지우기

                    # wiki이면 div 태그 이용해서 출력
                    elif render_stack[-1] == "wiki":
                        for idx, pattern in enumerate(part_res[::-1]):
                            if render_type[-1 - idx] == 'parsed':
                                continue
                            # 패턴이 없을 경우엔 중간지점이다. 그때엔 그냥
                            elif render_type[-1 - idx] == 'wiki' and not re.match(r"{{{#!wiki\s", pattern):
                                part_res[-1 - idx] = self.to_mw(pattern, True)
                                render_type[-1 - idx] = 'parsed'
                            # 패턴이 있으면 div태그 부착
                            elif render_type[-1 - idx] == "wiki" and re.match(r"{{{#!wiki\s", pattern):
                                pattern_style = pattern[10:].split('\n')[0]  # 패턴 스타일
                                pattern_remain = "\n".join(pattern[10:].split('\n')[1:])  # 나머지 부분
                                part_res[-1 - idx] = f"<div {pattern_style}>{self.to_mw(pattern_remain)}"
                                render_type[-1 - idx] = 'parsed'
                                break
                        # 마지막으로 pattern의 맨 마지막 부분은 div 태그를 닫는다
                        part_res[-1] += '</div>'
                        temp_preparsed = ""
                        r += 3
                        render_stack.pop()  # 스택 지우기

                    # folding이면 숨김 시작-끝 태그 사용
                    elif render_stack[-1] == "folding":
                        # for문 돌려보기
                        for idx, pattern in enumerate(part_res[::-1]):
                            if render_type[-1 - idx] == 'parsed':
                                continue
                            # 패턴이 없을 경우엔 중간지점이다. 그때엔 그냥 파싱한다
                            elif render_type[-1 - idx] == 'folding' and not re.match(r"{{{#!folding\s", pattern):
                                part_res[-1 - idx] = self.to_mw(pattern, True)
                                render_type[-1 - idx] = 'parsed'
                            # 패턴이 있으면 숨김 시작 틀 부착
                            elif render_type[-1 - idx] == "folding" and re.match(r"{{{#!folding\s", pattern):
                                pattern_title = pattern[13:].split('\n')[0]  # 패턴 스타일
                                pattern_remain = "\n".join(pattern[13:].split('\n')[1:])  # 나머지 부분
                                part_res[
                                    -1 - idx] = f"{{{{숨김 시작|title={self.inner_template(pattern_title)}}}}}\n{self.to_mw(pattern_remain)}"
                                render_type[-1 - idx] = 'parsed'
                                break
                        # 마지막으로 pattern의 맨 마지막 부분은 숨김 끝 태그 처리
                        part_res[-1] += "\n{{숨김 끝}}"
                        temp_preparsed = ""
                        r += 3
                        render_stack.pop()  # 스택 지우기

                    # syntax - syntaxhighlight 태그 사용
                    elif render_stack[-1] == "syntax":

                        for idx, pattern in enumerate(part_res[::-1]):
                            if render_type[-1 - idx] == 'parsed':
                                continue
                            # 패턴이 없을 경우엔 중간지점이다. 파싱하지 않는다.
                            elif render_type[-1 - idx] == 'syntax' and not re.match(r"{{{#!(syntax|source)\s",
                                                                                    pattern):
                                render_type[-1 - idx] = 'parsed'
                            # 패턴이 있으면 syntaxhighlight 태그 부착
                            elif render_type[-1 - idx] == "syntax" and re.match(r"{{{#!(syntax|source)\s", pattern):
                                pattern_title = pattern[12:].split('\n')[0]  # 패턴 스타일
                                pattern_remain = "\n".join(pattern[13:].split('\n')[1:])  # 나머지 부분
                                part_res[
                                    -1 - idx] = f"<syntaxhighlight lang=\"{self.inner_template(pattern_title)}\">\n{pattern_remain}"
                                render_type[-1 - idx] = 'parsed'
                                break
                        # 마지막으로 pattern의 맨 마지막 부분은 syntaxhighlight 태그 처리
                        part_res[-1] += "</syntaxhighlight>"
                        temp_preparsed = ""
                        r += 3
                        render_stack.pop()  # 스택 지우기

                    # 색상 표현 {{색}}틀 사용
                    elif render_stack[-1] == "color":
                        for idx, pattern in enumerate(part_res[::-1]):
                            if render_type[-1 - idx] == 'parsed':
                                continue
                            # 패턴이 없을 경우엔 중간지점이다. 위키 문법으로 파싱
                            elif render_type[-1 - idx] == 'color' and not re.match(r"{{{#([A-Za-z0-9,]+)\s",
                                                                                   pattern):
                                part_res[-1 - idx] = self.to_mw(pattern)
                                render_type[-1 - idx] = 'parsed'
                            # 패턴이 있으면 색 틀 사용
                            elif render_type[-1 - idx] == "color" and re.match(r"{{{#([A-Za-z0-9,]+)\s", pattern):
                                pattern_color = pattern[4:].split(' ')[0].split(',')[
                                    0]  # 색상 앞부분 확인. ,뒤의 다크모드 색상은 일단 미지원
                                if re.match(r"[A-Fa-f0-9]{6}", pattern_color):
                                    pattern_color = "#" + pattern_color[0:6]
                                elif re.match(r"[A-Fa-f0-9]{3,5}", pattern_color):
                                    pattern_color = '#' + pattern_color[0:3]
                                elif pattern_color not in WEB_COLOR_LIST.keys():
                                    pattern_color = 'black'  # 색깔 효과 무시
                                pattern_remain = " ".join(pattern[4:].split(" ")[1:])  # 나머지 부분
                                part_res[
                                    -1 - idx] = f"{{{{색|{pattern_color}|{self.inner_template(self.to_mw(pattern_remain, True))}"
                                render_type[-1 - idx] = 'parsed'
                                break
                        # 마지막으로 pattern의 맨 마지막 부분은 틀 닫기
                        part_res[-1] += "}}"
                        temp_preparsed = ""
                        r += 3
                        render_stack.pop()  # 스택 지우기

                    # 글씨 키우기/줄이기 -
                    elif render_stack[-1] == "size":
                        count_tag = 0
                        symbol = ""
                        for idx, pattern in enumerate(part_res[::-1]):
                            if render_type[-1 - idx] == 'parsed':
                                continue
                            # 패턴이 없을 경우엔 중간지점이다. 위키 문법으로 파싱
                            elif render_type[-1 - idx] == 'size' and not re.match(r"{{{[+\-][1-5]\s", pattern):
                                part_res[-1 - idx] = self.to_mw(pattern)
                                render_type[-1 - idx] = 'parsed'
                            # 패턴이 있으면 syntaxhighlight 태그 부착
                            elif render_type[-1 - idx] == "size" and re.match(r"{{{[+\-][1-5]\s", pattern):
                                symbol = pattern[3]
                                count_tag = int(pattern[4])
                                pattern_remain = pattern[6:]
                                if symbol == "+":
                                    part_res[-1 - idx] = "<big>" * count_tag + self.to_mw(pattern)
                                else:
                                    part_res[-1 - idx] = "<small>" * count_tag + self.to_mw(pattern)
                                render_type[-1 - idx] = 'parsed'
                                break
                        # 마지막으로 pattern의 맨 마지막 부분은 틀 닫기
                        part_res[-1] += "</big>" * count_tag if symbol == "+" else (
                            "</small>" * count_tag if symbol == "-" else "")
                        temp_preparsed = ""
                        r += 3
                        render_stack.pop()  # 스택 지우기

                    # 나머지 경우에는 그냥 더해준다.
                    else:
                        temp_preparsed += "}}}"
                        r += 3

                # 링크 처리 - 반드시 한 줄 안에서 닫혀 있어야 한다. link_processor 호출
                elif re.match(r"\[\[([^\n]*?)]]", text[r:]):
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    article = re.match(r"\[\[(.*?)(\|.*?)?]]", text[r:]).group(1)
                    if re.match(r"\[\[(.*?)(\|.*?)?]]", text[r:]).group(2):
                        cont = re.match(r"\[\[(.*?)(\|.*?)?]]", text[r:]).group(2)[1:]  # 앞의 |기호는 빼고 파싱해야 함.
                    else:
                        cont = ""
                    r += len(re.match(r"\[\[(.*?)]]", text[r:]).group(0))
                    part_res.append(self.link_processor(article, cont))
                    render_type.append("parsed")
                    temp_preparsed = ""

                # 수식 처리
                elif text[r:r + 6] == "[math(":
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    text_remain = text[6:]
                    closed_position = text_remain.find(")]")  # 닫기 괄호 위치
                    parsed = text_remain[:closed_position] if closed_position > 0 else text_remain
                    r += 8 + len(parsed) if closed_position >= 0 else 6 + len(parsed)
                    part_res.append("<math>" + parsed + "</math>")  # parsed
                    render_type.append("parsed")  # render_type
                    temp_preparsed = ""

                # 각주처리
                elif text[r:r + 2] == "[*":
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    temp_preparsed = "[*"
                    r += 2
                    render_stack.append('ref')

                # 매크로 - 닫혀 있어야 한다. 그리고 simple macro processor 호출
                elif re.match(r"\[([^\[*].*?)]", text[r:]):
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    cont = re.match(r"\[(.*?)]", text[r:]).group(1)
                    r += 2 + len(cont)
                    part_res.append(self.simple_macro_processor(cont))
                    render_type.append('parsed')
                    temp_preparsed = ""

                # 각주 닫기 처리
                elif letter == "]":
                    if len(render_stack) == 0:
                        part_res.append(self.to_mw(temp_preparsed+"]", True))
                        render_type.append('parsed')
                        temp_preparsed = ""
                        r += 1

                    elif render_stack[-1] == 'ref':
                        print('refTEST', part_res[-1], len(list(filter(lambda x: x=='ref', render_type))))
                        for idx, pattern in enumerate(part_res[::-1]):
                            if render_type[-1 - idx] == 'parsed':
                                continue
                            # 패턴이 없을 경우엔 중간지점이다. 위키 문법으로 파싱
                            elif render_type[-1 - idx] == 'ref' and not re.match(r"\[\*", pattern):
                                part_res[-1 - idx] = self.to_mw(pattern)
                                render_type[-1 - idx] = 'parsed'
                            # 패턴이 있으면 syntaxhighlight 태그 부착
                            elif render_type[-1 - idx] == "ref" and re.match(r"\[\*", pattern):
                                print('REF+TEST', part_res[-1-idx])
                                ref_name = re.match(r"\[\*(.*?)\s", pattern).group(1)
                                remain = re.match(r"\[*(.*?)\s(.*)", pattern).group(2)
                                part_res[-1 - idx] = f'''<ref name="{ref_name}">{self.to_mw(remain)}''' if ref_name != "" \
                                    else f'''<ref>{self.to_mw(remain)}'''
                                render_type[-1 - idx] = 'parsed'
                                break
                        # 마지막으로 pattern의 맨 마지막 부분은 틀 닫기
                        part_res[-1] += "</ref>"
                        temp_preparsed = ""
                        r += 1
                        render_stack.pop()  # 스택 지우기

                    else:
                        temp_preparsed += "]"
                        r += 1

                # 취소선1
                elif letter == "~" and re.match(r"~~(.*?)~~", text[r:]):
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    cont = re.match(r"~~(.*?)~~", text[r:]).group(1)
                    r += 4 + len(cont)
                    part_res.append(f"<del>{self.render_processor(cont)}</del>")
                    render_type.append('parsed')
                    temp_preparsed = ""

                # 취소선2
                elif letter == "-" and re.match(r"--(.*?)--", text[r:]):
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    cont = re.match(r"--(.*?)--", text[r:]).group(1)
                    r += 4 + len(cont)
                    part_res.append(f"<del>{self.render_processor(cont)}</del>")
                    render_type.append('parsed')
                    temp_preparsed = ''

                # 밑줄
                elif letter == "_" and re.match(r"__(.*?)__", text[r:]):
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    cont = re.match(r"__(.*?)__", text[r:]).group(1)
                    r += 4 + len(cont)
                    part_res.append(f"<u>{self.render_processor(cont)}</u>")
                    render_type.append('parsed')
                    temp_preparsed = ''

                # 위 첨자
                elif letter == "^" and re.match(r"\^\^(.*?)\^\^", text[r:]):
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    cont = re.match(r"\^\^(.*?)\^\^", text[r:]).group(1)
                    r += 4 + len(cont)
                    part_res.append(f"<sup>{self.render_processor(cont)}</sup>")
                    render_type.append('parsed')
                    temp_preparsed = ''

                # 아래첨자
                elif letter == "," and re.match(r",,(.*?),,", text[r:]):
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    cont = re.match(r",,(.*?),,", text[r:]).group(1)
                    r += 4 + len(cont)
                    part_res.append(f"<sub>{self.render_processor(cont)}</sub>")
                    render_type.append('parsed')
                    temp_preparsed = ''

                # 개행기호 - 앞부분의 내용을 전부 파싱...
                elif letter == "\n":
                    # 우선 앞에서 저장된 temp_preparsed 내용은 파싱한다.
                    render_stack_macro()
                    if re.match(r"^\n{2,}", text[r:], re.MULTILINE):
                        crlines = re.match(r"^\n{2,}", text[r:], re.MULTILINE).group(0)
                        part_res.append(crlines)  # 2행 이상 개행시에는 똑같이 개행
                        render_type.append('parsed')
                        r += len(crlines)
                        temp_preparsed = ""
                    elif r < len(text) - 1 and text[r + 1] != "\n":  # 한줄 개행이면 <br/>기호 삽입.
                        part_res.append("<br />")
                        render_type.append('parsed')
                        r += 1
                        temp_preparsed = ""
                    elif r == len(text) - 1:  # 마지막 글자가 개행문자면 그냥 개행문자로 처리
                        part_res.append("\n")
                        render_type.append('parsed')
                        r += 1
                        temp_preparsed = ""
                # 나머지 케이스
                else:
                    temp_preparsed += letter
                    r += 1
            # 나머지 케이스
            else:
                temp_preparsed += letter
                r += 1

        # 마지막으로 temp_preparsed 텍스트가 남아있으면 처리.
        if temp_preparsed != "":
            part_res.append(temp_preparsed)
            render_type.append("parsed")
            temp_preparsed = ""

        # 이제 render_stack이 남아있을 때 마저 처리
        while len(render_stack) > 0:

            print('RENDER_STACK_TEST', render_stack)

            # 파싱 타입에 따라 정리 - html이면 있는 그대로 출력
            if render_stack[-1] == "html":
                # 역순 추적
                for idx, pattern in enumerate(part_res[::-1]):
                    # html은 타입만 parsed로 바꾸고 내용을 바꾸지 않는다.
                    if render_type[-1 - idx] == 'html' and (
                            idx == len(part_res) - 1 or render_type[-2 - idx] == 'parsed'):
                        render_type[-1 - idx] = 'parsed'
                    elif render_type[-1 - idx] == 'parsed':
                        continue
                    else:
                        break
                render_stack.pop()  # 스택 지우기

            # wiki이면 div 태그 이용해서 출력
            elif render_stack[-1] == "wiki":
                for idx, pattern in enumerate(part_res[::-1]):
                    if render_type[-1 - idx] == 'parsed':
                        continue
                    # 패턴이 없을 경우엔 중간지점이다. 그때엔 그냥
                    elif render_type[-1 - idx] == 'wiki' and not re.match(r"{{{#!wiki\s", pattern):
                        part_res[-1 - idx] = self.to_mw(pattern, True)
                        render_type[-1 - idx] = 'parsed'
                    # 패턴이 있으면 div태그 부착
                    elif render_type[-1 - idx] == "wiki" and re.match(r"{{{#!wiki\s", pattern):
                        pattern_style = pattern[10:].split('\n')[0]  # 패턴 스타일
                        pattern_remain = "\n".join(pattern[10:].split('\n')[1:])  # 나머지 부분
                        part_res[-1 - idx] = f"<div {pattern_style}>{self.to_mw(pattern_remain)}"
                        render_type[-1 - idx] = 'parsed'
                        break
                # 마지막으로 pattern의 맨 마지막 부분은 div 태그를 닫는다
                part_res[-1] += '</div>'
                render_stack.pop()  # 스택 지우기

            # folding이면 숨김 시작-끝 태그 사용
            elif render_stack[-1] == "folding":
                # for문 돌려보기
                for idx, pattern in enumerate(part_res[::-1]):
                    if render_type[-1 - idx] == 'parsed':
                        continue
                    # 패턴이 없을 경우엔 중간지점이다. 그때엔 그냥 파싱한다
                    elif render_type[-1 - idx] == 'folding' and not re.match(r"{{{#!folding\s", pattern):
                        part_res[-1 - idx] = self.to_mw(pattern, True)
                        render_type[-1 - idx] = 'parsed'
                    # 패턴이 있으면 숨김 시작 틀 부착
                    elif render_type[-1 - idx] == "folding" and re.match(r"{{{#!folding\s", pattern):
                        pattern_title = pattern[13:].split('\n')[0]  # 패턴 스타일
                        pattern_remain = "\n".join(pattern[13:].split('\n')[1:])  # 나머지 부분
                        part_res[-1 - idx] = \
                            f"{{{{숨김 시작|title={self.inner_template(pattern_title)}}}}}\n{self.to_mw(pattern_remain)}"
                        render_type[-1 - idx] = 'parsed'
                        break
                # 마지막으로 pattern의 맨 마지막 부분은 숨김 끝 태그 처리
                part_res[-1] += "\n{{숨김 끝}}"
                render_stack.pop()  # 스택 지우기

            # syntax - syntaxhighlight 태그 사용
            elif render_stack[-1] == "syntax":

                for idx, pattern in enumerate(part_res[::-1]):
                    if render_type[-1 - idx] == 'parsed':
                        continue
                    # 패턴이 없을 경우엔 중간지점이다. 파싱하지 않는다.
                    elif render_type[-1 - idx] == 'syntax' and not re.match(r"{{{#!(syntax|source)\s",
                                                                            pattern):
                        render_type[-1 - idx] = 'parsed'
                    # 패턴이 있으면 syntaxhighlight 태그 부착
                    elif render_type[-1 - idx] == "syntax" and re.match(r"{{{#!(syntax|source)\s", pattern):
                        pattern_title = pattern[12:].split('\n')[0]  # 패턴 스타일
                        pattern_remain = "\n".join(pattern[13:].split('\n')[1:])  # 나머지 부분
                        part_res[-1 - idx] = \
                            f"<syntaxhighlight lang=\"{self.inner_template(pattern_title)}\">\n{pattern_remain}"
                        render_type[-1 - idx] = 'parsed'
                        break
                # 마지막으로 pattern의 맨 마지막 부분은 syntaxhighlight 태그 처리
                part_res[-1] += "</syntaxhighlight>"
                render_stack.pop()  # 스택 지우기

            # 색상 표현 {{색}}틀 사용
            elif render_stack[-1] == "color":
                for idx, pattern in enumerate(part_res[::-1]):
                    if render_type[-1 - idx] == 'parsed':
                        continue
                    # 패턴이 없을 경우엔 중간지점이다. 위키 문법으로 파싱
                    elif render_type[-1 - idx] == 'color' and not re.match(r"{{{#([A-Za-z0-9,]+)\s",
                                                                           pattern):
                        part_res[-1 - idx] = self.to_mw(pattern)
                        render_type[-1 - idx] = 'parsed'
                    # 패턴이 있으면 색 틀 사용
                    elif render_type[-1 - idx] == "color" and re.match(r"{{{#([A-Za-z0-9,]+)\s", pattern):
                        pattern_color = pattern[4:].split(' ')[0].split(',')[
                            0]  # 색상 앞부분 확인. ,뒤의 다크모드 색상은 일단 미지원
                        if re.match(r"[A-Fa-f0-9]{6}", pattern_color):
                            pattern_color = "#" + pattern_color[0:6]
                        elif re.match(r"[A-Fa-f0-9]{3,5}", pattern_color):
                            pattern_color = '#' + pattern_color[0:3]
                        elif pattern_color not in WEB_COLOR_LIST.keys():
                            pattern_color = 'black'  # 색깔 효과 무시
                        pattern_remain = " ".join(pattern[4:].split(" ")[1:])  # 나머지 부분
                        part_res[
                            -1 - idx] = f"{{{{색|{pattern_color}|{self.inner_template(self.to_mw(pattern_remain, True))}"
                        render_type[-1 - idx] = 'parsed'
                        break
                # 마지막으로 pattern의 맨 마지막 부분은 틀 닫기
                part_res[-1] += "}}"
                render_stack.pop()  # 스택 지우기

            # 글씨 키우기/줄이기 -
            elif render_stack[-1] == "size":
                count_tag = 0
                symbol = ""
                for idx, pattern in enumerate(part_res[::-1]):
                    if render_type[-1 - idx] == 'parsed':
                        continue
                    # 패턴이 없을 경우엔 중간지점이다. 위키 문법으로 파싱
                    elif render_type[-1 - idx] == 'size' and not re.match(r"{{{[+\-][1-5]\s", pattern):
                        part_res[-1 - idx] = self.to_mw(pattern)
                        render_type[-1 - idx] = 'parsed'
                    # 패턴이 있으면 syntaxhighlight 태그 부착
                    elif render_type[-1 - idx] == "size" and re.match(r"{{{[+\-][1-5]\s", pattern):
                        symbol = pattern[3]
                        count_tag = int(pattern[4])
                        pattern_remain = pattern[6:]
                        if symbol == "+":
                            part_res[-1 - idx] = "<big>" * count_tag + self.to_mw(pattern)
                        else:
                            part_res[-1 - idx] = "<small>" * count_tag + self.to_mw(pattern)
                        render_type[-1 - idx] = 'parsed'
                        break
                # 마지막으로 pattern의 맨 마지막 부분은 틀 닫기
                part_res[-1] += "</big>" * count_tag if symbol == "+" else (
                    "</small>" * count_tag if symbol == "-" else "")
                render_stack.pop()  # 스택 지우기

            # 각주
            elif render_stack[-1] == 'ref':
                for idx, pattern in enumerate(part_res[::-1]):
                    if render_type[-1 - idx] == 'parsed':
                        continue
                    # 패턴이 없을 경우엔 중간지점이다. 위키 문법으로 파싱
                    elif render_type[-1 - idx] == 'ref' and not re.match(r"\[\*", pattern):
                        part_res[-1 - idx] = self.to_mw(pattern)
                        render_type[-1 - idx] = 'parsed'
                    # 패턴이 있으면 ref 태그 부착
                    elif render_type[-1 - idx] == "size" and re.match(r"\[\*", pattern):
                        ref_name = re.match(r"\[*(.*?)\s", pattern).group(1)
                        remain = re.match(r"\[*(.*?)\s(.*)", pattern).group(2)
                        part_res[-1 - idx] = f'''<ref name="{ref_name}">{self.to_mw(remain)}'''
                        render_type[-1 - idx] = 'parsed'
                        break
                # 마지막으로 pattern의 맨 마지막 부분은 틀 닫기
                part_res[-1] += "</ref>"
                render_stack.pop()  # 스택 지우기

        res = "".join(part_res)

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
            # 내용이 비어 있지 않을 때 처리
            if list_line != "":
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
                if lvl < tbl['level']:
                    diff = tbl['level'] - lvl
                    tgn_total = tgn_total + "*" * diff if tbl['type'] == "ul" else tgn_total + "#" * diff
                    lvl = tbl['level']
                    tgn = tbl['type']
                    res += tgn_total + self.render_processor(tbl['preparsed']) + "\n"

                # 레벨 숫자가 앞의 숫자와 동일
                elif lvl == tbl['level'] and tgn == tbl['type']:
                    res += tgn_total + self.render_processor(tbl['preparsed']) + "\n"

                # 레벨 숫자가 앞의 숫자와 동일, 다른 타입
                elif lvl == tbl['level'] and tgn != tbl['type']:
                    tgn_total = tgn_total[:-1] + "*" if tbl['type'] == "ul" else tgn_total[:-1] + "#"
                    tgn = tbl['type']
                    res += tgn_total + self.render_processor(tbl['preparsed']) + "\n"

                # 레벨 숫자가 앞의 숫자보다 작음,
                elif lvl > tbl['level']:
                    # 우선 기호부터 확인해보자
                    tgn_total_level = tgn_total[tbl['level'] - 1]  # 해당 단계에서 심볼부터 확인

                    # 레벨 기준으로 확인
                    if (tgn_total_level == "*" and tbl['type'] == 'ul') or (
                            tgn_total_level == "#" and tbl['type'] == 'ol class="decimal"'):
                        # 그냥 컷을 함.
                        tgn_total = tgn_total[:tbl['level']]
                    else:
                        tgn_total = tgn_total[:tbl['level'] - 1] + "*" if tbl['type'] == 'ul' \
                            else tgn_total[:tbl['level'] - 1] + "#"

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
            for tg in self.LIST_TAG[1:]:
                if text[spacing:spacing + 2] == tg[0]:
                    res['type'] = tg[1]
                    res['preparsed'] = text[spacing + 2:]
                    break
        return res

    # 한 줄짜리 [매크로] 형식의 함수 처리하기
    def simple_macro_processor(self, text: str):
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
            return f"{{{{#ifexpr:{{{{#time:U|now}}}} - {{{{#time:U|{yr}-{mn}-{dy}}}}}>0|+}}}}\
            {{{{#expr:floor (({{{{#time:U|now}}}} - {{{{#time:U|{yr}-{mn}-{dy}}}}})/86400)}}}}"
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
            cont = re.match(r"ruby\((.*?)(,ruby=.*?)?(,color=.*?)?\)", text).group(1)
            ruby_part = re.match(r"ruby\((.*?)(,ruby=.*?)?(,color=.*?)?\)", text).group(2)
            color_part = re.match(r"ruby\((.*?)(,ruby=.*?)?(,color=.*?)?\)", text).group(3)
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
            res = f"{{{{{transcluding}" if ":" in transcluding else f"{{{{:{transcluding}"
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
            return f"{link}" if text == "" else f"[{link} {self.render_processor(text)}]"
        # 문단기호 링크에 대비
        elif re.match(r"$(.*?)#s-(.*)", link):
            article = re.match(r"$(.*?)#s-(.*)", link).group(1)
            paragraph = re.match(r"$(.*?)#s-(.*)", link).group(2)
            paragraph_list = paragraph.split(".")
            paragraph_name = self.find_paragraph_by_index(paragraph_list)
            return f"[[{article}#{paragraph_name}]]" if text == "" \
                else f"[[{article}#{paragraph_name}|{self.render_processor(text)}]]"

        else:
            return f"[[{link}]]" if text == "" else f"[[{link}|{self.render_processor(text)}]]"

    # 블록 파싱 함수
    # 우선 [br]태그로 다음 줄로 넘기는 방식은 사용하지 않으며, 맨 앞에 >가 있다는 것을 보증할 때에만 사용
    def bq_parser(self, text):
        print('function_start!!!')
        res = ''
        open_tag = '<blockquote style="border: 1px dashed grey; border-left: 3px solid #4188f1; padding:2px; margin:5px;">'
        close_tag = '</blockquote>'
        text_wo_bq = re.sub(r'>(.*?)(\n|$)', r'\1\2', text)  # 맨 앞 >기호 없애기
        idx = 0  # 첫 인덱스
        tmp_block = ''  # blockquote로 묶을 수 있는 부분인지 확인할 것.
        tmp_etc = ""  # blockquote 바깥의 부분
        print("text_wo_bq: ", text_wo_bq)
        print()
        while idx < len(text_wo_bq):
            # 첫 번째 개행 위치 찾기
            idx1 = text_wo_bq[idx:].find('\n')
            # 개행할 게 남아있으면
            if idx1 > -1:
                tmp_line = text_wo_bq[idx:idx + idx1 + 1]
                print("tmp_line : ", tmp_line, idx)
                # 만약 여전히 블록 안에 있을 때
                if re.match(r">(.*?)\n", tmp_line):
                    if tmp_etc != "":
                        res += self.render_processor(tmp_etc)
                        print("tmp_etc : ", tmp_etc)
                        tmp_etc = ""
                    tmp_block += tmp_line
                # blockquote 안에 없는 부분이면
                else:
                    if tmp_block != "":
                        res += self.bq_parser(tmp_block[:-1]) + '\n'  # 마지막줄이 아니므로 마지막 개행 기호 지우고 개행기호 붙이기
                        tmp_block = ""
                        print("tmp_block : ", tmp_block)
                    tmp_etc += tmp_line

                idx = idx + idx1 + 1  # 개행문자 다음에 추가

            # 마지막줄일 때 실행
            if idx1 == -1 or idx == len(text_wo_bq):
                print('endL--')
                tmp_line = text_wo_bq[idx:]
                print("tmp_line : ", tmp_line, idx)
                if re.match(r">(.*?)", tmp_line):
                    if tmp_etc != "":
                        res += self.render_processor(tmp_etc)
                        print("tmp_etc : ", tmp_etc)
                        tmp_etc = ""
                    tmp_block += tmp_line
                    print("tmp_block: ", tmp_block)
                    res += self.bq_parser(tmp_block)
                else:
                    if tmp_block != "":
                        res += self.bq_parser(tmp_block[:-1]) + '\n'  # 마지막줄이 아니므로 마지막 개행 기호 지우고 개행기호 붙이기
                        print("tmp_block : ", tmp_block)
                        tmp_block = ""
                    tmp_etc += tmp_line
                    print("tmp_etc: ", tmp_etc)
                    res += self.render_processor(tmp_etc)
                idx = len(text_wo_bq)

        print('function_end')
        return open_tag + '\n' + res + '\n' + close_tag

    # 표 매크로 함수
    # 각 셀에서 매크로 유도하는 함수
    # res, row_css, table_css, row_merginc_cell값 반환
    def table_macro(self, cell_text: str, row_merging_cell: int):
        cell_css = {'background-color': '', 'color': '', 'width': '', 'height': '', 'text-align': '',
                    'vertical-align': ''}
        row_css = {'background-color': '', 'color': '', 'height': ''}
        table_css = {'background-color': '', 'color': '', 'width': '', 'border-color': ''}
        # 파이프 문자 4개 사이의 텍스트일 때 -> 가로선
        if cell_text == "":
            return {"res": "", "row_css": row_css, "table_css": table_css, "row_merging_cell": row_merging_cell + 1}

        macro_pattern = re.match(r"(<[^>\n]+>)+(.*)", cell_text)
        res = '\n|'

        if macro_pattern:
            macro_iteration = re.finditer(r"<([^>\n]+)>", macro_pattern.group(1))
            # 우선 colspan부터 파악
            if row_merging_cell > 0:
                row_macro = re.search(r"<-([0-9]+)>", macro_pattern.group(1))
                row_macro_num = int(row_macro.group(1))
                res += ' colspan="{}"'.format(row_macro_num + row_merging_cell)

            # 매크로 패턴 파악
            for iter_pattern in macro_iteration:
                pattern_text = iter_pattern.group(1)
                # 가로줄 파악
                if row_merging_cell == 0 and re.match(r"-([0-9]+)", pattern_text):
                    rmerge = int(re.match(r"-([0-9]+)", pattern_text).group(1))
                    res += ' colspan="{}"'.format(rmerge) if rmerge > 1 else ''
                # 세로줄/ 세로 정렬 파악
                elif re.match(r"[\^v]?\|([0-9]+)", pattern_text):
                    valign = re.match(r"([\^v])?\|([0-9]+)", pattern_text).group(1)
                    vmerge = int(re.match(r"([\^v])?\|([0-9]+)", pattern_text).group(2))
                    valign_obj = {'^': 'top', 'v': 'bottom'}
                    cell_css['vertical-align'] = valign_obj[valign] if valign != "" else ""
                    res += ' rowspan="{}"'.format(vmerge) if vmerge > 1 else ''
                # 셀 가로정렬
                elif pattern_text in ["(", ":", ")"]:
                    talign_obj = {'(': 'left', ':': 'center', ')': 'right'}
                    cell_css['text-align'] = talign_obj[pattern_text]
                # 셀 너비
                elif re.match(r"width=(.+)", pattern_text):
                    width = re.match(r"width=(.+)", pattern_text).group(1)
                    cell_css['width'] = width
                # 셀 높이
                elif re.match(r"height=(.*)", pattern_text):
                    height = re.match(r"height=(.*)", pattern_text).group(1)
                    cell_css['height'] = height
                # 배경색
                elif re.match(r"bgcolor=(.*)", pattern_text):
                    bgcolor = re.match(r"bgcolor=(.*)", pattern_text).group(1)
                    cell_css['background-color'] = bgcolor
                # 글자색
                elif re.match(r"color=(.*)", pattern_text).group(1):
                    color = re.match(r"color=(.*)", pattern_text).group(1)
                    cell_css['color'] = color
                # 줄 배경색
                elif re.match(r"rowbgcolor=(.*)", pattern_text).group(1):
                    rowbgcolor = re.match(r"rowbgcolor=(.*)", pattern_text).group(1)
                    row_css['background-color'] = rowbgcolor
                # 줄 글자색
                elif re.match(r"rowcolor=(.*)", pattern_text).group(1):
                    rowcolor = re.match(r"rowcolor=(.*)", pattern_text).group(1)
                    row_css['color'] = rowcolor
                # 줄 높이
                elif re.match(r"rowheight=(.*)", pattern_text).group(1):
                    rowheight = re.match(r"rowheight=(.*)", pattern_text).group(1)
                    row_css['height'] = rowheight
                # 테이블 배경색
                elif re.match(r"table\s?bgcolor=(.*)", pattern_text).group(1):
                    tbgcolor = re.match(r"table\s?bgcolor=(.*)", pattern_text).group(1)
                    table_css['background-color'] = tbgcolor
                # 테이블 글자색
                elif re.match(r"table\s?color=(.*)", pattern_text).group(1):
                    tcolor = re.match(r"table\s?color=(.*)", pattern_text).group(1)
                    table_css['color'] = tcolor
                # 테이블 너비
                elif re.match(r"table\s?width=(.*)", pattern_text).group(1):
                    twidth = re.match(r"table\s?width=(.*)", pattern_text).group(1)
                    table_css['width'] = twidth
                # 테이블 테두리색
                elif re.match(r"table\s?bordercolor=(.*)", pattern_text).group(1):
                    tbdcolor = re.match(r"table\s?bordercolor=(.*)", pattern_text).group(1)
                    table_css['border-color'] = tbdcolor

            style_text = ''
            for key in cell_css:
                if cell_css[key] != "":
                    style_text += '{}:{};'.format(key, cell_css[key])
            style_text = 'style="{}"'.format(style_text) if style_text != "" else ""
            res = res + style_text + "|" if len(res) > 2 or style_text != "" else "\n|"

            remain_pattern = re.match(r"(<[^>\n]+>)+(.*)", cell_text).group(2)
            res += self.to_mw(remain_pattern)

        else:
            if row_merging_cell > 0:
                res += ' rowspan="{}"|'.format(row_merging_cell)

            res += self.to_mw(cell_text)

        return {"res": res, "row_css": row_css, "table_css": table_css, "row_merging_cell": 0}

    # 표 파싱 함수
    # 인자: text -> 나무마크 문서 데이터 중 표 부분만 따온 부분 텍스트(주의: 전체 문서 텍스트를 넣지 말 것!)
    # TODO: 정규표현식 최적화, 셀 내부 꾸미기 기능 구현
    def table_parser(self, text: str):
        # 캡션 매크로는 텍스트에서 하나만 있어야 한다. 두 개 이상 있을 경우 표를 나눈다.
        caption = ""
        if re.match(r"\|[^|\n]+\|", text):
            caption = re.match(r"\|([^|\n]+)\|", text).group(1)
            text = "||" + text[re.match(r"\|([^|\n]+)\|", text).end():]  # 캡션 매크로를 지운 패턴으로 변경
            # 또 같은 패턴이 발견된다면 표를 나누어서 출력합니다.
            if re.search(r"\n\|[^|\n]+\|", text):
                start_val = re.search(r"\n\|[^|\n]+\|", text).start()  # 패턴이 나타나는 표 위치
                return self.table_parser(text[:start_val]) + '\n' + self.table_parser(
                    text[start_val + 1:])

        # 우선 줄 단위로 나누어서 split
        text_row = text.split('||\n')
        # 셀 병합 및 '{| class="wikitable", '|+' |', '|-', '|}'등의 기호로 변형 : 최종 작업 단계
        result = '{| class="wikitable"\n|+{}'.format(caption) if caption != "" else '{|class="wikitable"'
        table_css = {'background-color': '', 'color': '', 'width': '', 'border-color': ''}

        # text_row가 ||로 안 끝나면 마지막 원소 무시
        if text_row[-1].strip()[-2:] != "||":
            text_row = text_row[:-1]

        for idx, row_text in enumerate(text_row):
            result_row = "\n|-"
            row_merging_cell = 0
            row_css = {'background-color': '', 'color': '', 'height': ''}
            cell_divide_list = row_text.split('||')  # 셀 단위로 나눈다

            if cell_divide_list[-1] == "":
                cell_divide_list = cell_divide_list[:-1]

            for cidx, cell_text in enumerate(cell_divide_list):
                table_css = self.table_macro(cell_text, row_merging_cell)['table_css']
                row_css = self.table_macro(cell_text, row_merging_cell)['row_css']
                row_merging_cell = self.table_macro(cell_text, row_merging_cell)['row_merging_cell']
                result_row += self.table_macro(cell_text, row_merging_cell)['res']

            # 셀별로
            style_text = ''
            for key in row_css:
                if row_css[key] != "":
                    style_text += '{}:{};'.format(key, row_css[key])
            style_text = 'style="{}"'.format(style_text) if style_text != "" else ""
            result_row = result_row.replace('|-', '|-{}'.format(style_text))
            result += result_row
            print('REMAINING - DEBUG')
            print("".join(text_row[idx + 1:]))

        style_text = ''
        for key in table_css:
            if table_css[key] != "":
                style_text += '{}:{};'.format(key, table_css[key])
        style_text = 'style="{}"'.format(style_text) if style_text != "" else ""
        result = result.replace('class="wikitable"', 'class="wikitable {}'.format(style_text))

        result += "\n|}"

        text = result
        print(text)
        return result

