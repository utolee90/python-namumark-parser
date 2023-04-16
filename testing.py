def do_render_footnote(self):
    global render_data, data_footnote

    footnote_num = 0
    footnote_regex = re.compile('(?:\[\*((?:(?!\[\*|\]| ).)+)?(?: ((?:(?!\[\*|\]).)+))?\])', re.I)
    footnote_count_all = len(re.findall(footnote_regex, render_data)) * 4
    while 1:
        footnote_num += 1

        footnote_data = re.search(footnote_regex, render_data)
        footnote_name = '' # 기본은 비어있음.
        footnote_text_data = '' # 각주 텍스트 데이터, 기본은 비어있음.

        if not footnote_data or footnote_count_all < 0:
            break
        else:
            # footnote_data_org = footnote_data.group(0) # 각주 데이터 전체
            footnote_data = footnote_data.groups() # (각주이름, 각주내용)

            footnote_num_str = str(footnote_num)

            if footnote_data[0]:
                footnote_name = footnote_data[0] # 각주 이름

            if footnote_data[1]:
                footnote_text_data = footnote_data[1] # 각주 텍스트

            if footnote_name in data_footnote:
                data_footnote[footnote_name]['list'] += [footnote_num_str]

                data_name = get_tool_data_storage(
                    '<ref name="' + footnote_name + '">' if footnote_name != '' else '<ref>',
                    '</ref>', footnote_text_data)

                render_data = re.sub(footnote_regex, '<' + data_name + '></' + data_name + '>',
                                         render_data, 1)
            else:
                data_footnote[footnote_name] = {}
                data_footnote[footnote_name]['list'] = [footnote_num_str]
                data_footnote[footnote_name]['data'] = footnote_text_data

                data_name = get_tool_data_storage(
                    '<ref name="' + footnote_name + '">' if footnote_name != '' else '<ref>',
                    '</ref>', footnote_text_data)

                render_data = re.sub(footnote_regex, '<' + data_name + '></' + data_name + '>',
                                          render_data, 1)

        footnote_count_all -= 1
