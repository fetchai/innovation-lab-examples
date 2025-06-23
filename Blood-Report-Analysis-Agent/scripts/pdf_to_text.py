
import PyPDF2
import os

def pdf_to_text(pdf_path, text_path):
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        with open(text_path, 'w', encoding='utf-8') as text_file:
            text_file.write(text)
        print(f"PDF converted to text and saved to {text_path}")
    except Exception as e:
        print(f"Error converting PDF to text: {e}")

if __name__ == "__main__":
    pdf_path = "input/blood_report.pdf"
    text_path = "input/blood_report.txt"
    pdf_to_text(pdf_path, text_path)
