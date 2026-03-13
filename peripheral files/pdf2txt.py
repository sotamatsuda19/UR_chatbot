import pdfplumber
import os

def pdf_to_txt(pdf_path, txt_path):

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_txt = ""
            
            for page in pdf.pages:
                page_txt = page.extract_text() or ""
                full_txt = full_txt + page_txt + "\n"

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_txt)

        print("successfully converted")


    except Exception as e:
        print(f"An error occurred {e}")

input_path = '/Users/sota/Desktop/App Development Hobby/curriculum/source.pdf'
output_path = '/Users/sota/Desktop/App Development Hobby/curriculum/output.txt'

    
pdf_to_txt(input_path, output_path)

