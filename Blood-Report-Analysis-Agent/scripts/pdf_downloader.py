
import requests
import os

def download_pdf_from_drive(drive_link, output_path):
    try:
        file_id = drive_link.split('/d/')[1].split('/')[0]
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        response = requests.get(download_url, stream=True)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"PDF downloaded to {output_path}")
        else:
            print(f"Failed to download PDF. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error downloading PDF: {e}")

if __name__ == "__main__":
    drive_link = ""
    os.makedirs("input", exist_ok=True)
    download_pdf_from_drive(drive_link, "input/blood_report.pdf")
