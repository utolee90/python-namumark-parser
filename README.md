# python-namumark-parser
php-namumark는 나무위키에서 사용되는 나무마크를 python 언어를 이용해서 HTML과 미디어위키 문법에 맞게 변환하는 도구입니다.

본 라이브러리는 koreapyj님의 [PHP-namumark](https://github.com/koreapyj/php-namumark) 를 참조해서 만들었습니다. 

주의! 아직 실행되지 않는 코드입니다. 실행이 될 때 재공지하겠습니다.

## 라이선스
본 라이브러리는 원본 소스에 따라 GNU Affero GPL 3.0에 따라 자유롭게 사용하실 수 있습니다. 

## 사용 방법
현재는 python 파일을 이용해서 텍스트 파일 하나를 HTML 코드와 미디어위키 문법으로 치환하는 기능을 제공하고 있습니다. 아직 완성되지 않은 점에 유의바랍니다.
	
### 일반 텍스트로 넘기는 경우

    # 우선 자신이 원하는 파일 제목을 지어줍시다. 예를 들면 천국.txt 파일을 작성합니다.

    # 다음과 같은 파이썬 코드를 실행합니다. 확장자는 제외합시다.
    > python main.py 천국 

    # 그러면 HTML.txt에는 HTML 파서가,  mw.txt에서는 미디어위키로 변환된 내용이 출력됩니다.
