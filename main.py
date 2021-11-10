from namumark import NamuMark
import sys

def main():
    # file_name
    if len(sys.argv) == 1:
        print("NEED FILE NAME")
    else:
        file_name = sys.argv[1]
        with open(f"{file_name}.txt", 'r', encoding='utf-8') as f1:
            cont = f1.read()

        file_dict = {
            "title": file_name,
            "text": cont
        }

        parser = NamuMark(file_dict)


        HTML = ""

        with open('HTML.txt', 'w', encoding='utf-8') as f2:
            f2.write(HTML, ensure_ascii=False)



if __name__ == "__main__":
    main()
