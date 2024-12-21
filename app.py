from flask import Flask, render_template, request, redirect, url_for,flash,send_from_directory,session,send_file,jsonify
import requests 
from docx import Document
import os
from pdf2docx import Converter
from docx2pdf import convert
from pytube import YouTube
from googleapiclient.discovery import build
from PyPDF2 import PdfReader, PdfWriter
import pikepdf
import json
import re
import tempfile
import base64
from io import BytesIO
from PyPDF2 import PdfMerger
from PIL import Image,ImageOps,ImageFile
import math
from dicttoxml import dicttoxml
import xml.dom.minidom
import xmltodict
import uuid
import shutil
import time
import cssutils
from bs4 import BeautifulSoup
import inflect
import string
import random
import secrets

app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

ImageFile.LOAD_TRUNCATED_IMAGES = True

BASE_UPLOAD_DIR = 'uploads'
BASE_DOWNLOAD_DIR = 'downloads'

os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)
os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)

INACTIVITY_TIMEOUT = 3600
p = inflect.engine()

# Conversion logic for different units
def convert_value(value, from_unit, to_unit, category):
    # Length conversion logic
    if category == 'length':
        if from_unit == 'm' and to_unit == 'km':
            return value / 1000
        elif from_unit == 'km' and to_unit == 'm':
            return value * 1000
        # Add other length unit conversion logic here...

    # Weight conversion logic
    elif category == 'weight':
        if from_unit == 'kg' and to_unit == 'g':
            return value * 1000
        elif from_unit == 'g' and to_unit == 'kg':
            return value / 1000
        # Add other weight unit conversion logic here...

    # Temperature conversion logic
    elif category == 'temperature':
        if from_unit == 'C' and to_unit == 'F':
            return (value * 9/5) + 32
        elif from_unit == 'F' and to_unit == 'C':
            return (value - 32) * 5/9
        elif from_unit == 'C' and to_unit == 'K':
            return value + 273.15
        elif from_unit == 'K' and to_unit == 'C':
            return value - 273.15
        # Add other temperature unit conversion logic here...

    return value

# Function to fetch exchange rates from the API
def get_exchange_rate(from_currency, to_currency):
    # Replace YOUR_API_KEY with the actual API key
    url = f"https://v6.exchangerate-api.com/v6/393fc6c7489952ffe5f7d33b/latest/{from_currency}"
    response = requests.get(url)
    data = response.json()
    
    if data['result'] == 'success':
        rates = data['conversion_rates']
        return rates.get(to_currency)
    return None
    
def delete_files_in_directory(directory):
    if os.path.exists(directory):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
            
def clean_inactive_user_directories():
    current_time = time.time()
    for root_dir in [BASE_UPLOAD_DIR, BASE_DOWNLOAD_DIR]:
        for user_dir in os.listdir(root_dir):
            user_dir_path = os.path.join(root_dir, user_dir)
            if os.path.isdir(user_dir_path):
                last_modified = os.path.getmtime(user_dir_path)
                if current_time - last_modified > INACTIVITY_TIMEOUT:
                    shutil.rmtree(user_dir_path, ignore_errors=True)

# Homepage route
@app.route('/')
def home():
    
    user_id = session.get('user_id')  # Get the user ID from the session
    if user_id:
        # Paths to user-specific directories
        user_upload_dir = os.path.join(BASE_UPLOAD_DIR, user_id)
        user_download_dir = os.path.join(BASE_DOWNLOAD_DIR, user_id)
        
        # Delete user-specific directories
        delete_files_in_directory(user_upload_dir)
        delete_files_in_directory(user_download_dir)
    
    return render_template('home.html')
    
@app.before_request
def setup_user_session():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())  # Generate a unique session ID
    
    # Create user-specific directories if they don't exist
    user_id = session['user_id']
    os.makedirs(os.path.join(BASE_UPLOAD_DIR, user_id), exist_ok=True)
    os.makedirs(os.path.join(BASE_DOWNLOAD_DIR, user_id), exist_ok=True)
    
    clean_inactive_user_directories()
    
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
    
@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template('413.html'), 413
    
@app.route('/about_us')
def about_us():
    return render_template('about_us.html')
    
@app.route('/contact_us')
def contact_us():
    return render_template('contact_us.html')
    
@app.route('/submit_contact',methods=['GET', 'POST'])
def submit_contact():
    return render_template('contact_us.html')

@app.route('/unit_conversion')
def unit_conversion():
    return render_template('unit_conversion.html')

@app.route('/convert_unit', methods=['POST'])
def convert_unit():
    category = request.form['category']
    from_unit = request.form['from_unit']
    to_unit = request.form['to_unit']
    value = float(request.form['value'])

    # Perform the conversion
    result = convert_value(value, from_unit, to_unit, category)

    # Return the result back to the template
    return render_template('unit_conversion.html', result=result, value=value, from_unit=from_unit, to_unit=to_unit)

@app.route('/currency_conversion')
def currency_conversion():
    return render_template('currency_conversion.html')

@app.route('/convert_currency', methods=['POST'])
def convert_currency():
    amount = float(request.form['amount'])
    from_currency = request.form['from_currency']
    to_currency = request.form['to_currency']
    
    # Get the exchange rate for the conversion
    exchange_rate = get_exchange_rate(from_currency, to_currency)
    
    if exchange_rate:
        converted_amount = amount * exchange_rate
        return render_template('currency_conversion.html', converted_amount=converted_amount, amount=amount, from_currency=from_currency, to_currency=to_currency)
    else:
        return render_template('currency_conversion.html', error="Currency conversion failed. Please try again.")
        
@app.route('/pdf_to_word', methods=['GET', 'POST'])
def pdf_to_word():
    docx_filename = None  # Initialize variable to store the output file name
    user_id = session['user_id']
    if request.method == 'POST':
        if 'pdf_file' not in request.files:
            return "No file uploaded", 400

        pdf_file = request.files['pdf_file']
        if pdf_file and pdf_file.filename.lower().endswith('.pdf'):
            # Ensure 'uploads' directory exists
            upload_folder = os.path.join(BASE_UPLOAD_DIR, user_id)
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)

            pdf_path = os.path.join(upload_folder, pdf_file.filename)
            print("Path",pdf_path)
            pdf_file.save(pdf_path)

            # Convert PDF to DOCX
            docx_filename = pdf_file.filename.rsplit('.', 1)[0] + '.docx'
            downloads_folder = os.path.join(BASE_DOWNLOAD_DIR, user_id)
            if not os.path.exists(downloads_folder):
                os.makedirs(downloads_folder)

            docx_path = os.path.join(downloads_folder, docx_filename)
            try:
                converter = Converter(pdf_path)  # Create a Converter instance
                converter.convert(docx_path, start=0, end=None)  # Convert entire PDF
                converter.close()
            except Exception as e:
                return f"Error during conversion: {str(e)}", 500

    # Render the same HTML file and pass the generated DOCX filename (if available)
    return render_template('pdf_to_word.html', docx_filename=docx_filename)
       
@app.route('/word_to_pdf', methods=['GET', 'POST'])
def word_to_pdf():
    docx_filename = None  # Initialize docx_filename to handle the GET request case.
    user_id = session['user_id']
    if request.method == 'POST':
        # Handle DOCX file upload
        docx_file = request.files['docx_file']
        
        # Check if the file is a DOCX file
        if docx_file and docx_file.filename.endswith('.docx'):
            docx_filename = docx_file.filename
            docx_path = os.path.join(os.path.join(BASE_UPLOAD_DIR, user_id), docx_filename)
            
            # Save the DOCX file
            docx_file.save(docx_path)
            
            # Convert DOCX to PDF
            try:
                # Define the output PDF file path
                pdf_filename = docx_filename.replace('.docx', '.pdf')
                pdf_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), pdf_filename)
                
                # Perform the conversion
                convert(docx_path, pdf_path)  # This converts DOCX to PDF
                
                # Provide a download link to the generated PDF
                return render_template('word_to_pdf.html', pdf_filename=pdf_filename)
            
            except Exception as e:
                return f"Error during conversion: {str(e)}"
        else:
            return "Invalid file format. Please upload a .docx file."
            
    # Render the same HTML file and pass the generated DOCX filename (if available)
    return render_template('word_to_pdf.html', docx_filename=docx_filename)

@app.route('/download/<filename>')
def download_file(filename):
    user_id = session['user_id']
    return send_from_directory(os.path.join(BASE_DOWNLOAD_DIR, user_id), filename, as_attachment=True)
    

# Google API Key (replace with your actual API key)
API_KEY = "AIzaSyDLdwAZ9M-42__M5kcxTZzr0UBFwnavGhY"

# YouTube Data API service name and version
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

@app.route('/youtube_tags', methods=['GET', 'POST'])
def youtube_tags():
    tags = None  # To store the tags fetched from the video
    error = None  # To store any errors
    video_title = None  # To store the video title
    video_thumbnail = None  # To store the video thumbnail URL

    if request.method == 'POST':
        video_url = request.form.get('video_url') # Get URL from the form
        
        if video_url:
            try:
                # Extract the video ID from the URL
                video_id = extract_video_id(video_url)
                if not video_id:
                    error = "Error: please enter a valid YouTube video URL"
                else:
                    # Call YouTube Data API to fetch tags
                    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
                    response = youtube.videos().list(part="snippet", id=video_id).execute()
                    tags = response['items'][0]['snippet'].get('tags', [])
                    video_title = response['items'][0]['snippet']['title']
                    video_thumbnail = response['items'][0]['snippet']['thumbnails']['high']['url']
                    
                    if not tags:
                        error = "No tags found for this video."
            except Exception as e:
                # Handle any API or parsing errors
                error = "Unable to fetch tags for this video. Please check the URL or try again later."

    return render_template('youtube_tags.html', tags=tags, error=error,title=video_title, thumbnail=video_thumbnail)

def extract_video_id(url):
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0]
    else:
        return None
        
# Route for the PDF encryption form
@app.route('/protect_pdf', methods=['GET', 'POST'])
def protect_pdf():
    encrypted_pdf_path = None
    error = None
    user_id = session['user_id']
    if request.method == 'POST':
        # Get the uploaded PDF file and the password
        pdf_file = request.files.get('pdf_file')
        password = request.form.get('password')

        if not pdf_file:
            error = "Please upload a PDF file."
        elif not password:
            error = "Please provide the password to unlock the PDF."
        elif not pdf_file.filename.lower().endswith('.pdf'):
            error = "Uploaded file is not a valid PDF."
        else:
            pdf_file = request.files['pdf_file']
            if pdf_file and pdf_file.filename.lower().endswith('.pdf'):
                # Ensure 'uploads' directory exists
                upload_folder = os.path.join(BASE_UPLOAD_DIR, user_id)
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)

                pdf_path = os.path.join(upload_folder, pdf_file.filename)
                filename = pdf_file.filename
                pdf_file.save(pdf_path)
            try:
                encrypted_pdf_path = encrypt_pdf(pdf_path, password, filename)
            except Exception as e:
                print(e)
                error = "There is an issue while encrypting the PDF. Please try again later."

    return render_template('protect_pdf.html', encrypted_pdf_path=encrypted_pdf_path, error=error)


# Function to encrypt the PDF with a password
def encrypt_pdf(pdf_path, password, filename):
    user_id = session['user_id']
    # Create PDF reader and writer
    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    # Add all pages to the writer
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        writer.add_page(page)

    # Set a password for the encrypted PDF
    encrypted_pdf_filename = f"encrypted_{filename}"
    encrypted_pdf_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), encrypted_pdf_filename)
    
    # Write the encrypted PDF to the output path
    with open(encrypted_pdf_path, 'wb') as encrypted_file:
        writer.encrypt(password)
        writer.write(encrypted_file)

    return encrypted_pdf_filename
    
@app.route('/unlock_pdf', methods=['GET', 'POST'])
def unlock_pdf():
    processed_pdf_filename = None
    error = None
    user_id = session['user_id']

    if request.method == 'POST':
        # Get the uploaded PDF file and the password
        pdf_file = request.files.get('pdf_file')
        password = request.form.get('password')

        # Validate file and password input
        if not pdf_file:
            error = "Please upload a PDF file."
        elif not password:
            error = "Please provide the password to unlock the PDF."
        elif not pdf_file.filename.lower().endswith('.pdf'):
            error = "Uploaded file is not a valid PDF."
        else:
            # Save the uploaded PDF to the uploads folder
            pdf_path = os.path.join(os.path.join(BASE_UPLOAD_DIR, user_id), pdf_file.filename)
            pdf_file.save(pdf_path)

            # Define output path for decrypted PDF
            processed_pdf_filename = f"unlocked_{pdf_file.filename}"
            processed_pdf_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), processed_pdf_filename)

            try:
                # Attempt to open and decrypt the PDF with the provided password
                with pikepdf.open(pdf_path, password=password) as pdf:
                    # Save the decrypted PDF to the output path
                    pdf.save(processed_pdf_path)
            except pikepdf.PasswordError:
                error = "Incorrect password. Please try again with the correct password."
            except Exception as e:
                error = "There is an issue while decrypting the PDF. Please try again later."

    return render_template('unlock_pdf.html',processed_pdf_filename=processed_pdf_filename,error=error)
    
app.secret_key = 'zentools_zentools@123'
ACCESS_USERNAME = 'zentools'
ACCESS_PASSWORD = "zentools@100599"
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        username = request.form.get('username')
        if password == ACCESS_PASSWORD and username == ACCESS_USERNAME:
            session['authenticated'] = True  # Store authentication status in session
            return redirect(url_for('paid_tools'))
        else:
            flash("Incorrect password. Please try again.", "error")
    return render_template('login.html')
    
@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('home'))
    
@app.route('/paid_tools')
def paid_tools():
    if session.get('authenticated'):  # Check if the user is authenticated
        return render_template('paid_tools.html')
    else:
        flash("You must log in to access this page.", "error")
        return redirect(url_for('login'))

@app.route('/jsonformatter', methods=['GET', 'POST'])
def jsonformatter():
    formatted_json = None
    error_message = None
    json_input = ''

    if request.method == 'POST':
        json_input = request.form.get('json_input')

        if json_input:
            try:
                # Attempt to parse JSON directly
                parsed_json = json.loads(json_input)
            except json.JSONDecodeError:
                # Try to fix common issues
                try:
                    corrected_json_input = json_input.strip()  # Remove leading/trailing whitespace

                    # Fix unquoted keys
                    corrected_json_input = re.sub(
                        r"(?<![\[{,])\s*([a-zA-Z_][\w]*)\s*:(?![^\[{])", r'"\1":', corrected_json_input
                    )
                    
                    # Convert single quotes to double quotes
                    corrected_json_input = corrected_json_input.replace("'", '"')
                    corrected_json_input = corrected_json_input.replace("False", 'false').replace("True", 'true').replace("None", '"None"')
                    
                    # Remove trailing commas in arrays/objects
                    corrected_json_input = re.sub(r",(\s*[\]}\]])", r"\1", corrected_json_input)

                    # Attempt to parse corrected JSON
                    parsed_json = json.loads(corrected_json_input)
                except json.JSONDecodeError as e:
                    error_message = "Invalid JSON please enter valid JSON"
                    parsed_json = None

            if parsed_json:
                # Pretty print the JSON with 3-space indentation
                formatted_json = json.dumps(parsed_json, indent=3)
        else:
            error_message = "Please enter JSON data."

    return render_template('jsonformatter.html', formatted_json=formatted_json, error_message=error_message,json_input=json_input)

@app.route('/merge_pdf', methods=['GET', 'POST'])
def merge_pdf():
    merged_pdf_filename = None
    user_id = session['user_id']
    if request.method == 'POST':
        files = request.files.getlist('pdf_files')
        if len(files) < 2:
            return "Please upload at least two PDF files."

        # Save the uploaded files
        filenames = []
        for file in files:
            filename = os.path.join(os.path.join(BASE_UPLOAD_DIR, user_id), file.filename)
            file.save(filename)
            filenames.append(filename)

        # Merge the PDFs
        
        merged_pdf_filename = 'Zentools_merged.pdf'
        merged_pdf = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id),merged_pdf_filename )
        merger = PdfMerger()
        for filename in filenames:
            merger.append(filename)
        merger.write(merged_pdf)
        merger.close()

        # Provide the merged PDF URL for downloading
        return render_template('merge_pdf.html', merged_pdf_filename=merged_pdf_filename)

    return render_template('merge_pdf.html')
    
    
@app.route('/image_to_base64', methods=['GET', 'POST'])
def image_to_base64():
    base64_string = None
    if request.method == 'POST' and 'image_file' in request.files:
        image_file = request.files['image_file']

        if image_file and image_to_base64_allowed_file(image_file.filename):
            # Read the image and convert to Base64
            img = image_file.read()
            base64_string = base64.b64encode(img).decode('utf-8')  # Convert to Base64 string
            
    return render_template('image_to_base64.html', base64_string=base64_string)

# Helper function to check allowed file extensions
def image_to_base64_allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    

@app.route('/base64_to_image', methods=['GET', 'POST'])
def base64_to_image():
    image_path = None
    filename = None
    error_message = None
    user_id = session['user_id']
    if request.method == 'POST' and 'base64_string' in request.form:
        base64_string = request.form['base64_string'].strip()
        try:
            # Remove Base64 header if present
            if base64_string.startswith("data:image"):
                base64_string = base64_string.split(",", 1)[1]

            # Decode the Base64 string
            img_data = base64.b64decode(base64_string)

            # Save the image in the downloads folder
            filename = "decoded_image.jpg"
            image_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), filename)
            with open(image_path, 'wb') as f:
                f.write(img_data)

        except Exception as e:
            error_message = "Please enter a valid Base64 string."

    return render_template('base64_to_image.html',image_path=image_path,filename=filename,error_message=error_message)
    
    
@app.route('/compress_image', methods=['GET', 'POST'])
def compress_image():
    compressed_image_path = None
    error_message = None
    compressed_image_filename = None
    user_id = session['user_id']
    if request.method == 'POST' and 'image_file' in request.files:
        image_file = request.files['image_file']
        
        if image_file:
            try:
                # Get the original file extension
                file_extension = image_file.filename.rsplit('.', 1)[1].lower()

                # Map JPG/JPEG to JPEG format (PIL expects 'JPEG' for both)
                if file_extension == 'jpg' or file_extension == 'jpeg':
                    pil_format = 'JPEG'
                else:
                    pil_format = file_extension.upper()  # Use the extension directly for other formats

                # Open the image using PIL
                img = Image.open(image_file)
                
                width, height = img.size
                new_size = (width//2, height//2)
                img = img.resize(new_size)
                
                # Set the output file path with the same extension
                compressed_image_filename = f'compressed_image.{file_extension}'
                compressed_image_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), f'compressed_image.{file_extension}')
                
                # Compress the image (adjust quality)
                img.save(compressed_image_path, format=pil_format, quality=50,optimize=True)
                
            except Exception as e:
                error_message = "There is an issue while compressing the uploaded image."

    return render_template('compress_image.html', compressed_image_path=compressed_image_path, error_message=error_message,compressed_image_filename=compressed_image_filename)
    
    
@app.route('/invert_image', methods=['GET', 'POST'])
def invert_image():
    inverted_image_path = None
    error_message = None
    inverted_image_filename = None
    user_id = session['user_id']
    if request.method == 'POST' and 'image_file' in request.files:
        image_file = request.files['image_file']
        
        if image_file:
            try:
                # Get the original file extension
                file_extension = image_file.filename.rsplit('.', 1)[1].lower()

                # Open the image using PIL
                img = Image.open(image_file).convert('RGB')  # Ensure image is in RGB mode
                
                # Invert the image colors
                inverted_img = ImageOps.invert(img)
                
                # Set the output file path
                inverted_image_filename = f'inverted_image.{file_extension}'
                inverted_image_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), inverted_image_filename)
                
                # Save the inverted image
                inverted_img.save(inverted_image_path)
                
            except Exception as e:
                error_message = "There is an issue while inverting the uploaded image."

    return render_template('invert_image.html',inverted_image_path=inverted_image_path,error_message=error_message,inverted_image_filename=inverted_image_filename)
    
    
@app.route('/convert_to_black_and_white', methods=['GET', 'POST'])
def convert_to_black_and_white():
    bw_image_path = None
    error_message = None
    bw_image_filename = None
    user_id = session['user_id']
    if request.method == 'POST' and 'image_file' in request.files:
        image_file = request.files['image_file']
        
        if image_file:
            try:
                # Get the original file extension
                file_extension = image_file.filename.rsplit('.', 1)[1].lower()

                # Open the image using PIL
                img = Image.open(image_file)
                
                # Convert the image to black and white (grayscale)
                bw_img = img.convert('L')
                
                # Set the output file path
                bw_image_filename = f'bw_image.{file_extension}'
                bw_image_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), bw_image_filename)
                
                # Save the black and white image
                bw_img.save(bw_image_path)
                
            except Exception as e:
                error_message = "There is an issue while converting the uploaded image to black and white."

    return render_template('convert_to_black_and_white.html',bw_image_path=bw_image_path,error_message=error_message,bw_image_filename=bw_image_filename)
    
    
@app.route('/youtube_thumbnail_grabber', methods=['GET', 'POST'])
def youtube_thumbnail_grabber():
    error = None
    video_title = None
    thumbnail_urls = {}
    thumbnail_filenames = {}
    user_id = session['user_id']
    if request.method == 'POST':
        video_url = request.form.get('video_url')
        
        if video_url:
            try:
                video_id = extract_video_id(video_url)
                if not video_id:
                    error = "Error: please enter a valid YouTube video URL"
                else:
                    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
                    response = youtube.videos().list(part="snippet", id=video_id).execute()
                    video_title = response['items'][0]['snippet']['title']
                    thumbnails = response['items'][0]['snippet']['thumbnails']

                    # Extract all available thumbnails and order them
                    all_thumbnails = {
                        'HD': thumbnails.get('maxres', {}),
                        'Standard': thumbnails.get('standard', {}),
                        'High': thumbnails.get('high', {}),
                        'Medium': thumbnails.get('medium', {}),
                    }

                    # Save the images and store URLs
                    for size, thumbnail in all_thumbnails.items():
                        if thumbnail:
                            thumbnail_urls[size] = thumbnail['url']
                            thumbnail_filename = f'{video_id}_{size}.jpg'
                            thumbnail_filenames[size] = thumbnail_filename
                            file_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), thumbnail_filename)
                            img_response = requests.get(thumbnail_urls[size])
                            if img_response.status_code == 200:
                                with open(file_path, 'wb') as f:
                                    f.write(img_response.content)
                            else:
                                error = "Unable to fetch the thumbnail image."
                    if not thumbnail_urls:
                        error = "No thumbnails found for this video."
            except Exception as e:
                error = "Unable to fetch thumbnail for this video. Please check the URL or try again later."

    return render_template('youtube_thumbnail_grabber.html', error=error, title=video_title, thumbnail_urls=thumbnail_urls,thumbnail_filenames=thumbnail_filenames)


@app.route('/convert_jpg_to_png', methods=['GET', 'POST'])
def convert_jpg_to_png():
    png_image_path = None
    error_message = None
    png_image_filename = None
    user_id = session['user_id']
    if request.method == 'POST' and 'image_file' in request.files:
        image_file = request.files['image_file']
        
        if image_file:
            try:
                # Get the original file extension
                file_extension = image_file.filename.rsplit('.', 1)[1].lower()

                # Check if the uploaded file is a JPG
                if file_extension != 'jpg' and file_extension != 'jpeg':
                    error_message = "Only JPG or JPEG files are allowed for conversion."
                    return render_template('convert_jpg_to_png.html', error_message=error_message)
                
                # Open the image using PIL
                img = Image.open(image_file)
                
                # Set the output file path for PNG
                png_image_filename = f'{os.path.splitext(image_file.filename)[0]}.png'
                png_image_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), png_image_filename)
                
                # Save the image as PNG
                img.save(png_image_path, 'PNG')
                
            except Exception as e:
                error_message = "There is an issue while converting the JPG image to PNG."

    return render_template('convert_jpg_to_png.html', png_image_path=png_image_path, error_message=error_message, png_image_filename=png_image_filename)

@app.route('/convert_png_to_jpg', methods=['GET', 'POST'])
def convert_png_to_jpg():
    jpg_image_path = None
    error_message = None
    jpg_image_filename = None
    user_id = session['user_id']
    if request.method == 'POST' and 'image_file' in request.files:
        image_file = request.files['image_file']
        
        if image_file:
            try:
                # Get the original file extension
                file_extension = image_file.filename.rsplit('.', 1)[1].lower()

                # Check if the uploaded file is a PNG
                if file_extension != 'png':
                    error_message = "Only PNG files are allowed for conversion."
                    return render_template('convert_png_to_jpg.html', error_message=error_message)
                
                # Open the image using PIL
                img = Image.open(image_file)
                
                # Set the output file path for JPG
                jpg_image_filename = f'{os.path.splitext(image_file.filename)[0]}.jpg'
                jpg_image_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), jpg_image_filename)
                
                # Convert image mode to 'RGB' (JPG does not support transparency)
                if img.mode in ("RGBA", "P"): 
                    img = img.convert("RGB")
                
                # Save the image as JPG
                img.save(jpg_image_path, 'JPEG')
                
            except Exception as e:
                error_message = "There is an issue while converting the PNG image to JPG."

    return render_template('convert_png_to_jpg.html', jpg_image_path=jpg_image_path, error_message=error_message, jpg_image_filename=jpg_image_filename)


@app.route('/convert_webp_to_jpg', methods=['GET', 'POST'])
def convert_webp_to_jpg():
    jpg_image_path = None
    error_message = None
    jpg_image_filename = None
    user_id = session['user_id']
    if request.method == 'POST' and 'image_file' in request.files:
        image_file = request.files['image_file']
        
        if image_file:
            try:
                # Get the original file extension
                file_extension = image_file.filename.rsplit('.', 1)[1].lower()

                # Check if the uploaded file is a WEBP
                if file_extension != 'webp':
                    error_message = "Only WEBP files are allowed for conversion."
                    return render_template('convert_webp_to_jpg.html', error_message=error_message)
                
                # Open the image using PIL
                img = Image.open(image_file)
                
                # Set the output file path for JPG
                jpg_image_filename = f'{os.path.splitext(image_file.filename)[0]}.jpg'
                jpg_image_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), jpg_image_filename)
                
                # Convert image mode to 'RGB' (JPG does not support transparency)
                if img.mode in ("RGBA", "P"): 
                    img = img.convert("RGB")
                
                # Save the image as JPG
                img.save(jpg_image_path, 'JPEG')
                
            except Exception as e:
                error_message = "There is an issue while converting the WEBP image to JPG."

    return render_template('convert_webp_to_jpg.html', jpg_image_path=jpg_image_path, error_message=error_message, jpg_image_filename=jpg_image_filename)
    
    
@app.route('/convert_jpgs_to_pdf', methods=['GET', 'POST'])
def convert_jpgs_to_pdf():
    pdf_file_path = None
    error_message = None
    pdf_filename = None
    user_id = session['user_id']
    if request.method == 'POST' and 'image_files' in request.files:
        image_files = request.files.getlist('image_files')  # Retrieve multiple files

        if image_files:
            try:
                images = []
                base_name = os.path.splitext(image_files[0].filename)[0]  # Use the name of the first image as base

                for image_file in image_files:
                    # Get the file extension
                    file_extension = image_file.filename.rsplit('.', 1)[1].lower()

                    # Check if the uploaded file is a JPG or JPEG
                    if file_extension not in ['jpg', 'jpeg']:
                        error_message = "Only JPG or JPEG files are allowed for conversion."
                        return render_template('convert_jpgs_to_pdf.html', error_message=error_message)

                    # Open the image using PIL
                    img = Image.open(image_file)

                    # Convert image mode to RGB if required
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")

                    images.append(img)

                # Set the output file path for PDF using the base name
                pdf_filename = f"{base_name}.pdf"
                pdf_file_path = os.path.join(os.path.join(BASE_DOWNLOAD_DIR, user_id), pdf_filename)

                # Save all images as a single PDF
                images[0].save(pdf_file_path, "PDF", resolution=100.0, save_all=True, append_images=images[1:])

            except Exception as e:
                error_message = "There was an issue while converting the JPG images to PDF."
                print(e)

    return render_template('convert_jpgs_to_pdf.html', pdf_file_path=pdf_file_path, error_message=error_message, pdf_filename=pdf_filename)
    
    
@app.route('/convert_json_to_xml', methods=['GET', 'POST'])
def convert_json_to_xml():
    xml_data = ''
    error_message = ''
    json_data = ''
    
    if request.method == 'POST':
        json_data = request.form.get('json_data')
        try:
            data_dict = json.loads(json_data)
            xml_data = dicttoxml(data_dict, ids=False).decode()
        except Exception as e:
            error_message = f"There is an issue while converting to XML. Please check your json."
        
    return render_template('convert_json_to_xml.html', xml_data=xml_data, error_message=error_message,json_data=json_data)
    
@app.route('/json_minify', methods=['GET', 'POST'])
def json_minify():
    json_data = ''
    minified_json = ''
    error_message = ''

    if request.method == 'POST':
        json_data = request.form.get('json_data')
        try:
            minified_json = json.dumps(json.loads(json_data), separators=(',', ':'))
        except Exception as e:
            print(f"Error while minifying JSON: {str(e)}")
            error_message = "There is an issue with your JSON input. Please check and try again."

    return render_template('json_minify.html', json_data=json_data, minified_json=minified_json, error_message=error_message)
    
 
def beautify_css(css_data):
    try:
        css_parser = cssutils.parseString(css_data)
        beautified_css = ""
        for rule in css_parser:
            selector = rule.selectorText
            properties = rule.style
            beautified_css += f"{selector} {{\n"
            for property in properties:
                beautified_css += f"    {property.name}: {property.value};\n"
            beautified_css += "}\n\n"
        
        return beautified_css.strip()
    except Exception as e:
        return None

        
@app.route('/css_beautify', methods=['GET', 'POST'])
def css_beautify():
    css_data = ''
    beautified_css = ''
    error_message = ''

    if request.method == 'POST':
        if 'css_data' in request.form:
            css_data = request.form.get('css_data')
            beautified_css = beautify_css(css_data)
            if not beautified_css:
                error_message = "There is an issue with your CSS input. Please check and try again."

    return render_template('css_beautify.html', css_data=css_data, beautified_css=beautified_css, error_message=error_message)
    
    
@app.route('/html_beautify', methods=['GET', 'POST'])
def html_beautify():
    html_data = ''
    beautified_html = ''
    error_message = ''
    
    if request.method == 'POST':
        html_data = request.form.get('html_data')
        try:
            if html_data:
                soup = BeautifulSoup(html_data, 'html.parser')
                beautified_html = soup.prettify()
            else:
                error_message = "No HTML input provided."
        except:
            error_message = "There is an issue with your HTML input. Please check and try again."
            
    return render_template('html_beautify.html', html_data=html_data, beautified_html=beautified_html, error_message=error_message)
    

@app.route('/Character_counter')
def Character_counter():
    return render_template('Character_counter.html')

@app.route('/count_Character', methods=['POST'])
def count_Character():
    text = request.json.get('text', '')
    char_count = len(text)
    word_count = len(text.split())
    return jsonify({
        'char_count': char_count,
        'word_count': word_count
    })
    
@app.route('/number_to_words')
def number_to_words():
    return render_template('number_to_words.html')

@app.route('/convert_in_words', methods=['POST'])
def convert_in_words():
    number = request.json.get('number', '').replace(',', '')
    try:
        number_in_words = p.number_to_words(int(number)).replace(',', '')
        number_in_words = ' '.join(word.capitalize() for word in number_in_words.replace('-', ' ').split())
    except ValueError:
        number_in_words = "Invalid input"
    return jsonify({
        'number_in_words': number_in_words
    })
    

@app.route('/password-generator')
def password_generator():
    return render_template('password_generator.html')

@app.route('/generate-password', methods=['POST'])
def generate_password():
    data = request.json
    length = int(data.get('length', 12))  # Default length is 12 if not provided

    # Validate the length (ensure it's within the range of 8 to 48)
    if length < 8 or length > 48:
        return jsonify({'password': 'Password length must be between 8 and 48 characters!'}), 400

    # Define the character sets for each type of character
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    numbers = string.digits
    symbols = string.punctuation

    # Initialize the pool of characters based on selected checkboxes
    password_characters = ""
    if data.get('lowercase'):
        password_characters += lowercase
    if data.get('uppercase'):
        password_characters += uppercase
    if data.get('numbers'):
        password_characters += numbers
    if data.get('symbols'):
        password_characters += symbols

    if not password_characters:
        return jsonify({'password': 'No criteria selected!'}), 400

    password = ''.join(secrets.choice(password_characters) for _ in range(length))

    return jsonify({'password': password})
    
@app.route('/lowercase_text')
def lowercase_text():
    return render_template('lowercase.html')
    
@app.route('/uppercase_text')
def uppercase_text():
    return render_template('uppercase.html')

   
if __name__ == '__main__':
    app.run(debug=True)
