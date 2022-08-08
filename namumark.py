import re

# from template import WEB_COLOR_LIST


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

    # 파서 태그 -
    PARSER_TAG = [
        r"{{{#!wiki .*?\n",
        r"{{{#!folding .*?\n",
        r"{{{(#[A-Za-z0-9,]) ",
        r"{{{([+\-][1-5]) ",
        r"\[\[",
        r"\[\*",
        r"\[([A-Za-z가-힣]+)"
    ]

    # 파서 태그 라인
    PARSER_TAG_LINE = [
        r"'''''",
        r"'''",
        r"''",
        r"__",
        r"~~",
        r"--",
        r"\^\^",
        r",,"
    ]

    # 반드시 맨 첫줄에 와야 하는 파서 태그
    PARSER_TAG_CR = [
        r"\n\u0020+(\*|1\.|A\.|I\.|i\.)",
        r"\n>",
        r"\n\|[^\s]"
    ]

    # macro value
    PARSER_TAG_MACRO = [
        'wiki',
        'folding',
        'color',
        'size',
        'link',
        'ref',
        'macro'
    ]

    #
    PARSER_TAG_LINE_MACRO = [
        'bold-italic',
        'bold',
        'italic',
        'underline',
        'strike',
        'strike2',
        'sup',
        'sub'
    ]

    PARSER_TAG_CR_MACRO = [
        'list',
        'bq',
        'table'
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

    # 매크로 맵 - 결과
    # {"position": [[시작,끝], [시작,끝],... ], "value":[매크로1, 매크로2, ...]
    def macro_map(self, text: str):

        forced_return = False  # 처음에 개행기호 집어넣기
        if text[0] != '\n':
            text = '\n' + text  # 문법 원활하게 처리하기 위해 텍스트 처음에 개행기호 집어넣기
            forced_return = True

        txt_length = len(text)  # 길이
        txt_lines = list(map(lambda x: x + '\n', text.split('\n')))  # 글을 출력하기
        txt_lines[-1] = txt_lines[-1][:-1]  # 마지막 \n 지우기
        txt_position = [len("".join(txt_lines[:k])) for k, val in enumerate(txt_lines)]  # 글의 위치값
        res = {"position": [], "value": []}
        macro_stack = []
        i = int(forced_return)  # 낱자 번호
        frn = int(forced_return)  # 위치 정할 때 사용.
        ln = 0  # 줄 번호

        while i < txt_length:

            # 가로선 매크로
            if re.match(r"\n-{4,10}(\n|$)", text[i - 1:]):
                pattern_end = re.match(r"(^|\n)-{4,10}\n", text[i - 1:]).end()
                res['position'].append([i - frn, i + pattern_end - 1 - frn])
                res['value'].append('hr')
                i += pattern_end - 1

            # 헤더 매크로
            elif re.match(r"\n=.*?=\s*(\n|$)", text[i - 1:]):
                pattern_end = re.match(r"\n=.*?=\s*\n", text[i - 1:]).end()
                res['position'].append([i - frn, i + pattern_end - 1 - frn])
                res['value'].append('header')
                i += pattern_end - 1

            # 주석 매크로
            elif re.match(r"\n##(\n|$)", text[i - 1:]):
                pattern_end = re.match(r"\n##(\n|$)", text[i - 1:]).end()
                res['position'].append([i - frn, i + pattern_end -1 - frn])
                res['value'].append('comment')
                i += pattern_end - 1

            # nowiki/pre 매크로
            elif re.match(r"{{{([^#+\-]|[+\-][^12345]|#[^!0-9A-Za-z])", text[i:]):
                # 줄에 있으면
                if re.search(r"}}}[^}]", txt_lines[ln]):
                    closed_pos = re.search(r"}}}[^}]", text[i:]).start()
                    res['position'].append([i - frn, i + closed_pos + 3 - frn])
                    res['value'].append('nowiki')
                    i += closed_pos + 3 - frn
                else:
                    closed_pos = re.search(r"}}}", text[i:]).start()
                    res['position'].append([i - frn, i + closed_pos + 3 - frn])
                    res['value'].append('pre')
                    i += closed_pos + 3 - frn

            # html 매크로
            elif re.match(r"{{{#!html", text[i:]):
                closed_pos = re.search(r"}}}", text[i:]).start()
                res['position'].append([i - frn, i + closed_pos + 3 - frn])
                res['value'].append('html')
                i += closed_pos + 3 - frn

            # syntax/source 매크로
            elif re.match(r"{{{#!(syntax|source)", text[i:]):
                closed_pos = re.search(r"}}}", text[i:]).start()
                res['position'].append([i - frn, i + closed_pos + 3 - frn])
                res['value'].append('syntax')
                i += closed_pos + 3 - frn

            # 나머지
            else:
                # 줄의 처음에 시작하는 매크로 분석
                for cri, tag1 in enumerate(self.PARSER_TAG_CR):
                    if re.match(tag1, text[i - 1:]):
                        macro_stack.append([self.PARSER_TAG_CR_MACRO[cri], i - frn])
                        i += re.match(tag1, text[i - 1:]).end() - 1
                        break
                else:

                    # linear_parser_tag 분석
                    for pli, tag2 in enumerate(self.PARSER_TAG_LINE):
                        if re.match(tag2, text[i:]):
                            if len(macro_stack) > 0 and macro_stack[-1][0] == self.PARSER_TAG_LINE_MACRO[pli]:
                                macro_val = macro_stack.pop()
                                res['position'].append([macro_val[1], i + 3 - frn])
                                res['value'].append(self.PARSER_TAG_LINE_MACRO[pli])
                                i += len(tag2)
                            else:
                                macro_stack.append([self.PARSER_TAG_LINE_MACRO[pli], i - frn])
                                i += len(tag2)
                            break

                    else:

                        # 파서 태그 분석
                        for pi, tag3 in enumerate(self.PARSER_TAG):
                            if re.match(tag3, text[i:]):
                                macro_stack.append([self.PARSER_TAG_MACRO[pi], i - frn])
                                i += re.match(tag3, text[i:]).end()
                                break
                        else:
                            # 닫히는 태그인지 확인해보자
                            if len(macro_stack) > 0:
                                cur_macro = macro_stack[-1][0]
                                MACRO_RENDER_PROCESSOR = ['wiki', 'folding', 'color', 'size']

                                if i < txt_length - 2 and cur_macro in MACRO_RENDER_PROCESSOR and text[
                                                                                                  i:i + 3] == "}}}":

                                    macro_val = macro_stack.pop()
                                    res['position'].append([macro_val[1], i + 3 - frn])
                                    res['value'].append(macro_val[0])
                                    i += 3
                                elif i < txt_length - 1 and cur_macro == "link" and text[i:i + 2] == "]]":

                                    macro_val = macro_stack.pop()
                                    res['position'].append([macro_val[1], i + 2 - frn])
                                    res['value'].append(macro_val[0])
                                    i += 2
                                elif cur_macro in ['ref', 'macro'] and text[i] == "]":

                                    macro_val = macro_stack.pop()
                                    res['position'].append([macro_val[1], i + 1 - frn])
                                    res['value'].append(macro_val[0])
                                    i += 1

                                elif cur_macro == 'table' and re.match(r"\|\|(\n[^|]|\n$|$)", text[i:]):
                                    macro_val = macro_stack.pop()
                                    res['position'].append(
                                        [macro_val[1], i + 3 - frn] if i < txt_length - 3 else [macro_val[1],
                                                                                                i + 2 - frn])
                                    res['value'].append(macro_val[0])
                                    i += 3 if i < txt_length - 3 else 2

                                elif cur_macro == 'list' and (
                                        re.match(r"($|\n$|\n{2})", text[i:]) or re.match(r"\n[^\u0020]",
                                                                                         text[i:]) or re.match(
                                        r"\n\u0020+[^*1AIi]", text[i:])):
                                    macro_val = macro_stack.pop()
                                    res['position'].append([macro_val[1], i + 1 - frn])
                                    res['value'].append(macro_val[0])
                                    i += 1

                                elif cur_macro == 'bq' and (
                                        i == txt_length - 1 or (text[i] == '\n' and text[i + 1] != ">")):
                                    macro_val = macro_stack.pop()
                                    res['position'].append([macro_val[1], i + 1 - frn])
                                    res['value'].append(macro_val[0])
                                    i += 1

                                elif cur_macro == 'comment' and (
                                        i < txt_length - 2 or (text[i] == '\n' and text[i + 1:i + 3] != '##')):
                                    macro_val = macro_stack.pop()
                                    res['position'].append([macro_val[1], i + 1 - frn])
                                    res['value'].append(macro_val[0])
                                    i += 1

                                elif i > 0 and text[i] == '\n' and text[i - 1] != '\n' and text[i - 1] != '\n' and set(
                                        map(lambda x: x[0], macro_stack)).isdisjoint(
                                        {'table', 'list', 'bq', 'comment'}):
                                    res['position'].append([i - frn, i + 1 - frn])
                                    res['value'].append('br')
                                    i += 1
                                else:
                                    i += 1
                            else:
                                i += 1
            # ln값 재조정
            if ln < len(txt_position) and i > txt_position[ln]:
                ln = len(list(filter(lambda x: x < i, txt_position)))

        res['remain_stack'] = macro_stack
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

    def to_mw(self, text: str):
        # 결과
        result = ""
        # 파서 하나 적용할 결과
        parser_result = ""
        # 텍스트를 줄 단위로 나눈 뒤 매크로 맵을 산출
        macros = self.macro_map(text)
        macros_positions = macros['position']
        macros_value = macros['value']

        new_macros = []
        for ix, val in enumerate(macros_positions):
            inclusion = False
            for x in new_macros:
                if val[0] >= x[1] and val[1] <=x[2]:
                    inclusion = True
            if not inclusion:
                new_macros.append([macros_value[ix], val[0], val[1]])

        r = 0
        mx = 0
        MACRO_RENDER_PROCESSOR = ['html', 'wiki', 'folding', 'syntax', 'color', 'size', 'pre']
        MACRO_TEXT_PROCESSOR = ["bold-italic", "bold", "italic", "underline",
                                "strike", "strike2", "sup", "sub", "nowiki"]

        tmp = 0

        print(new_macros)
        while r < len(text) and mx < len(new_macros):
            tmp = r
            start_val = new_macros[mx][1]
            end_val = new_macros[mx][2]
            if r == start_val:
                macro_val = new_macros[mx][0]
                # r, mx 바꿔주기
                def get_next():
                    nonlocal r, mx
                    r = end_val
                    mx += 1
                # 매크로 값에 따라 정의하기
                if macro_val == "header":
                    result += self.header_processor(text[start_val:end_val])
                    get_next()
                elif macro_val in ["hr", "comment"]:
                    result += self.misc_processor(text[start_val:end_val])
                    get_next()
                elif macro_val == "list":
                    result += self.list_parser(text[start_val:end_val])
                    get_next()
                elif macro_val == "table":
                    result += self.table_parser(text[start_val:end_val])
                    get_next()
                elif macro_val == "bq":
                    result += self.bq_parser(text[start_val:end_val])
                    get_next()
                elif macro_val in MACRO_TEXT_PROCESSOR:
                    result += self.text_processor(text[start_val:end_val])
                    get_next()
                elif macro_val == "link":
                    use_text = text[start_val:end_val]
                    link_val = re.match(r"\[\[(.*?)(\|.*?)?]]", use_text).group(1)
                    express_cont = re.match(r"\[\[(.*?)(\|.*?)?]]", use_text).group(2) # 맨 앞에 |기호 제외
                    express_cont = express_cont[1:] if express_cont else ""
                    result += self.link_processor(link_val, express_cont)
                    get_next()
                elif macro_val == "macro":
                    result += self.simple_macro_processor(text[start_val:end_val])
                    get_next()
                elif macro_val == "ref":
                    result += self.ref_processor(text[start_val:end_val])
                    get_next()
                elif macro_val in MACRO_RENDER_PROCESSOR:
                    result += self.render_processor(text[start_val:end_val])
                    get_next()
                elif macro_val == "br":
                    result += "<br/ >"
                    get_next()

            else:
                result += text[r]
                r += 1

            if tmp == r:
                raise Exception("INFINITY LOOF:::{}번째 문자에서 문제 발생. ({},{})".format(r, mx, new_macros[mx]))

        result += text[r:]  #나머지는 파싱 안 되므로 그냥 더해줌.

        return result


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

        return res

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

    # 텍스트 프로세서 - 닫힐 때에만 정확히 잡아주자
    def text_processor(self, text: str):
        # 굵게 기울임 - 글자 바꾸지 않기
        if re.match(r"'''''", text):
            return "'''''"+self.to_mw(text[5:-5] if text[-5:] == "'''''" else text[5:])+"'''''"
        # 굵게 - 글짜 바꾸지 않기
        elif re.match(r"'''", text):
            return "'''"+self.to_mw(text[3:-3] if text[-3:] == "'''" else text[3:])+"'''"
        # 기울임
        elif re.match(r"''", text):
            return "''"+self.to_mw(text[2:-2] if text[-2:] == "''" else text[2:])+"''"
        # 밑줄
        elif re.match(r"__", text):
            return "<u>"+self.to_mw(text[2:-2] if text[-2:] == "__" else text[2:])+"</u>"
        # 취소선
        elif re.match(r"~~", text):
            return "<del>"+self.to_mw(text[2:-2] if text[-2:] == "~~" else text[2:])+"</del>"
        # 취소선2
        elif re.match(r"--", text):
            closed = text[2:].find("--")
            return "<del>"+self.to_mw(text[2:-2] if text[-2:] == "--" else text[2:])+"</del>"
        # 위첨자
        elif re.match(r"\^\^", text):
            return "<sup>"+self.to_mw(text[2:-2] if text[-2:] == "^^" else text[2:])+"</sup>"
        # 아래첨자
        elif re.match(r",,", text):
            return "<sub>"+self.to_mw(text[2:-2] if text[-2:] == ",," else text[2:])+"</sub>"
        # 문법 리터럴
        elif re.match(r"{{{", text):
            return "<nowiki>"+self.to_mw(text[3:-3] if text[-3:] == "}}}" else text[3:])+"</nowiki>"
        # 나머지
        else:
            return self.to_mw(text)

    # 중괄호 여러줄 프로세싱. 기본적으로 문법 기호 포함.
    def render_processor(self, text: str):

        # HTML
        if re.match(r"{{{#!html (.*)}}}", text, re.MULTILINE):
            inner_text = re.match(r"{{{#!html (.*)}}}", text, re.MULTILINE).group(1)
            return "<div>"+inner_text + "</div>"
        # wiki
        elif re.match(r"{{{#!wiki (.*?)\n(.*)}}}", text, re.MULTILINE):
            inner_tag = re.match(r"{{{#!wiki (.*?)\n(.*)}}}", text, re.MULTILINE).group(1)
            inner_content = re.match(r"{{{#!wiki (.*?)\n(.*)}}}", text, re.MULTILINE).group(2)
            return f"<div {inner_tag}>{self.to_mw(inner_content)}</div>"

        # folding
        elif re.match(r"{{{#!folding (.*?)\n(.*)}}}", text, re.MULTILINE):
            hiding_title = re.match(r"{{{#!folding (.*?)\n(.*)}}}", text, re.MULTILINE).group(1)
            inner_content = re.match(r"{{{#!folding (.*?)\n(.*)}}}", text, re.MULTILINE).group(2)
            return f"{{{{숨김 시작|title={hiding_title}}}}}\n{self.to_mw(inner_content)}\n{{{{숨김 끝}}}}"

        # syntax/source
        elif re.match(r"{{{#!syntax (.*?)\n(.*)}}}", text, re.MULTILINE):
            lang = re.match(r"{{{#!syntax (.*?)\n(.*)}}}", text, re.MULTILINE).group(1)
            content = re.match(r"{{{#!syntax (.*?)\n(.*)}}}", text, re.MULTILINE).group(2)
            return f"<syntaxhighlight lang=\"{lang}\">\n{content}\n</syntaxhighlight>"

        # color
        elif re.match(r"{{{#[A-Za-z0-9]+(,[A-Za-z0-9]+)? ", text):
            color = re.match(r"{{{#([A-Za-z0-9]+)(,[A-Za-z0-9]+)? ", text).group(1)
            content = re.match(r"{{{#([A-Za-z0-9]+)(,[A-Za-z0-9]+)? (.*)}}}", text).group(3)
            if re.match(r"[0-9a-fA-F]{3}", color) or re.match(r"[0-9a-fA-F]{6}", color):
                color = "#"+color   # #기호 붙이기
            return f"{{{{색|{color}|{self.inner_template(self.to_mw(content))}}}}}"

        # size
        elif re.match(r"{{{[+\-][1-5] ", text):
            size_symbol = re.match(r"{{{([+\-])([1-5]) ", text).group(1)
            size_level = int(re.match(r"{{{([+\-])([1-5]) ", text).group(2))
            remaining = re.match(r"{{{([+\-])([1-5]) (.*)}}}", text).group(3)
            size_tag = "big" if size_symbol == "+" else "small"
            return f"<{size_tag}>"*size_level + self.to_mw(remaining) + f"</{size_tag}>"*size_level

        # pre
        elif re.match(r"{{{", text):
            remaining_text = re.match(r"{{{(.*)}}}", text, re.MULTILINE).group(1)
            return f"<pre>{remaining_text}\n</pre>"

        # 나머지 - 파싱하지 않음.
        else:
            return text


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
                    res += tgn_total + self.to_mw(tbl['preparsed']) + "\n"

                # 레벨 숫자가 앞의 숫자와 동일
                elif lvl == tbl['level'] and tgn == tbl['type']:
                    res += tgn_total + self.to_mw(tbl['preparsed']) + "\n"

                # 레벨 숫자가 앞의 숫자와 동일, 다른 타입
                elif lvl == tbl['level'] and tgn != tbl['type']:
                    tgn_total = tgn_total[:-1] + "*" if tbl['type'] == "ul" else tgn_total[:-1] + "#"
                    tgn = tbl['type']
                    res += tgn_total + self.to_mw(tbl['preparsed']) + "\n"

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
                    res += tgn_total + self.to_mw(tbl['preparsed']) + "\n"

        else:
            for tbl in list_table:
                # 같은 레벨, 같은 태그명
                if lvl == tbl['level'] and tgn == tbl['type']:
                    res += f"<li>{self.to_mw(tbl['preparsed'])}</li>\n"
                # 같은 레벨, 태그명만 다를 때
                elif lvl == tbl['level'] and tgn != tbl['type']:
                    # 태그 닫기
                    res += f"</{tgn[0:2]}>\n"
                    tgn = tbl['type']
                    open_tag_list[-1] = tgn
                    res += f"<{tbl['type']}>\n"
                    res += f"<li>{self.to_mw(tbl['preparsed'])}</li>\n"
                # 레벨값보다 수준이 더 클 때
                elif lvl + 1 == tbl['level']:
                    res += f"<{tbl['type']}>\n"
                    res += f"<li>{self.to_mw(tbl['preparsed'])}</li>\n"
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
                        res += f"<li>{self.to_mw(tbl['preparsed'])}</li>\n"
                        tgn = tbl['type']
                    else:
                        res += f"</{open_tag_list[-1][0:2]}>\n"
                        res += f"<{tbl['type']}>\n"
                        res += f"<li>{self.to_mw(tbl['preparsed'])}</li>\n"
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

    # 각주 처리 - 각주 안에 각주가 있을 때 처리 추가
    def ref_processor(self, text: str):
        if re.match(r"\[\*", text):
            ref_name = re.match(r"\[\*([^\s\]]*?)", text).group(1) # 각주 이름. *앞에 표시된 부분
            # 공백이 있을 때 - 각주의 내용이 있음.
            if re.match(r"\[\*([^\s\]]*?) ", text):
                ref_val = re.match(r"\[\*([^\s\]]*?) (.*)(]|$)", text).group(2)  # 각주 내용
                return f"<ref name\"={ref_name}\">{ref_val}</ref>" \
                    if ref_name != "" else f"<ref>{ref_val}</ref>"
            else:
                return f"<ref name=\"{ref_name}\"/>"
        else:
            return self.to_mw(text)


    # [매크로] 형식의 함수 처리하기
    def simple_macro_processor(self, text: str):
        const_macro_list = {
            "br": "<br />",
            "date": "{{#timel:Y-m-d H:i:sP}}",
            "datetime": "{{#timel:Y-m-d H:i:sP}}",
            # "목차": "__TOC__",  # 일단 표시. 그러나 목차 길이가 충분히 길면 지울 생각
            # "tableofcontents": "__TOC__",
            # "각주": "<references/ >",  # 리브레 위키에서는 <references/> 대신 {{각주}} 틀 사용
            # "footnote": "<references/ >",  # 리브레 위키에서는 <references/> 대신 {{각주}} 틀 사용
            "각주": "{{각주}}",
            "footnote": "{{각주}}",
            "clearfix": "{{-}}",
            "pagecount": "{{NUMBEROFPAGES}}",
            "pagecount(문서)": "{{NUMBEROFARTICLES}}",
        }
        # 단순 텍스트일 때
        if text in const_macro_list.keys():
            return const_macro_list[text]

        # 목차 길이가 충분히 길면 표시하지 않는다.
        elif text in ['목차', 'tableofcontents']:
            return "__TOC__" if len(self.get_toc()) <= 5 else ""

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
        # 책갈피 기호
        elif re.match(r"anchor\((.*)\)", text):
            aname = re.match(r"anchor\((.*)\)", text).group(1)
            return f"<span id=\"{aname}\"></span>"
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

        # youtube/nicovideo 틀 - YouTube 확장기능 의존
        elif re.match(r"(youtube|nicovideo)\((.*)\)", text):
            conts_type = re.match(r"(youtube|nicovideo)\((.*)\)", text).group(1)
            conts = re.match(r"(youtube|nicovideo)\((.*)\)", text).group(2)
            conts_list = conts.split(',')
            conts_id = conts_list[0].strip() #유튜브 id
            conts_width = ""
            conts_height = ""
            for txt in conts_list[1:]:
                if txt[0:6] == "width=":
                    conts_width = txt[6:]
                elif txt[0:7] == 'height=':
                    conts_height = txt[7:]
            return f"{{{{#tag:{conts_type}|{conts_id}|width={conts_width}|height={conts_height}}}}}"

        else:
            return ""

    # 한 줄짜리 링크형태 문법 처리
    def link_processor(self, link, text):
        # 외부 링크
        if re.match(r"https?://(.*)", link):
            return f"{link}" if text == "" else f"[{link} {self.to_mw(text)}]"
        # 문단기호 링크에 대비
        elif re.match(r"$(.*?)#s-(.*)", link):
            article = re.match(r"$(.*?)#s-(.*)", link).group(1)
            paragraph = re.match(r"$(.*?)#s-(.*)", link).group(2)
            paragraph_list = paragraph.split(".")
            paragraph_name = self.find_paragraph_by_index(paragraph_list)
            # article이 비어있거나 문서명과 같을 때는
            if article == "" or article == self.WIKI_PAGE:
                return f"[[#{paragraph_name}]]" if text == ""\
                    else f"[[#{paragraph_name}|{self.to_mw(text)}]]"
            # article이 다른 거면 문단명을 알 수 없으므로 일단 파싱하지 않는다.
            else:
                return f"[[{article}#s-{paragraph}]]" if text == "" \
                    else f"[[{article}#s-{paragraph}|{self.to_mw(text)}]]"

        else:
            return f"[[{link}]]" if text == "" else f"[[{link}|{self.to_mw(text)}]]"

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
                        res += self.to_mw(tmp_etc)
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
                        res += self.to_mw(tmp_etc)
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
                    res += self.to_mw(tmp_etc)
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
                if row_macro:
                    row_macro_num = int(row_macro.group(1))
                else:
                    row_macro_num = 1
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
                    cell_css['vertical-align'] = valign_obj.get(valign) if valign != "" else ""
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
                elif re.match(r"color=(.*)", pattern_text):
                    color = re.match(r"color=(.*)", pattern_text).group(1)
                    cell_css['color'] = color
                # 줄 배경색
                elif re.match(r"rowbgcolor=(.*)", pattern_text):
                    rowbgcolor = re.match(r"rowbgcolor=(.*)", pattern_text).group(1)
                    row_css['background-color'] = rowbgcolor
                # 줄 글자색
                elif re.match(r"rowcolor=(.*)", pattern_text):
                    rowcolor = re.match(r"rowcolor=(.*)", pattern_text).group(1)
                    row_css['color'] = rowcolor
                # 줄 높이
                elif re.match(r"rowheight=(.*)", pattern_text):
                    rowheight = re.match(r"rowheight=(.*)", pattern_text).group(1)
                    row_css['height'] = rowheight
                # 테이블 배경색
                elif re.match(r"table\s?bgcolor=(.*)", pattern_text):
                    tbgcolor = re.match(r"table\s?bgcolor=(.*)", pattern_text).group(1)
                    table_css['background-color'] = tbgcolor
                # 테이블 글자색
                elif re.match(r"table\s?color=(.*)", pattern_text):
                    tcolor = re.match(r"table\s?color=(.*)", pattern_text).group(1)
                    table_css['color'] = tcolor
                # 테이블 너비
                elif re.match(r"table\s?width=(.*)", pattern_text):
                    twidth = re.match(r"table\s?width=(.*)", pattern_text).group(1)
                    table_css['width'] = twidth
                # 테이블 테두리색
                elif re.match(r"table\s?bordercolor=(.*)", pattern_text):
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
        if style_text != "":
            result = result.replace('class="wikitable"', 'class="wikitable" {}'.format(style_text))

        result += "\n|}"

        text = result
        print(text)
        return result

