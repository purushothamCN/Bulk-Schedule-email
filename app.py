from flask import Flask, render_template, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
import csv
import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'txt'}
app.config['DATABASE'] = 'emails.db'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Initialize database
def init_db():
    with sqlite3.connect(app.config['DATABASE']) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS scheduled_emails
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      smtp_server TEXT NOT NULL,
                      smtp_port INTEGER NOT NULL,
                      smtp_username TEXT NOT NULL,
                      smtp_password TEXT NOT NULL,
                      subject TEXT NOT NULL,
                      body TEXT NOT NULL,
                      is_html BOOLEAN NOT NULL,
                      emails TEXT NOT NULL,
                      send_time DATETIME NOT NULL,
                      status TEXT DEFAULT 'pending')''')
        conn.commit()

init_db()

class EmailSender:
    def __init__(self, smtp_server, smtp_port, username, password):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    def send_email(self, to_email, subject, body, is_html=True):
        footer = """
        <h2 style="font-size: 18px; font-weight: bold;">
            Best Regards,<br>
            Purushotham CN<br>
            Automated Mail<br>
        </h2>
        """
        body_with_footer = body + footer

        msg = MIMEMultipart()
        msg['From'] = self.username
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body_with_footer, 'html' if is_html else 'plain'))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True, None
        except Exception as e:
            return False, str(e)

    def send_bulk_emails(self, emails, subject, body, is_html=True):
        results = []
        for email in emails:
            success, error = self.send_email(email, subject, body, is_html)
            results.append({
                'email': email,
                'success': success,
                'error': error if not success else None
            })
        return results

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def read_emails_from_file(filepath):
    emails = []
    try:
        with open(filepath, 'r') as file:
            if filepath.endswith('.csv'):
                reader = csv.reader(file)
                for row in reader:
                    if row:  # Skip empty rows
                        emails.extend([email.strip() for email in row if '@' in email])
            else:  # txt file
                for line in file:
                    if '@' in line:
                        emails.append(line.strip())
    except Exception as e:
        print(f"Error reading file: {e}")
    return emails

def process_scheduled_email(email_id):
    with sqlite3.connect(app.config['DATABASE']) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scheduled_emails WHERE id=?", (email_id,))
        email_job = cursor.fetchone()
        
        if not email_job or email_job[10] != 'pending':  # status column
            return
        
        # Update status to processing
        cursor.execute("UPDATE scheduled_emails SET status='processing' WHERE id=?", (email_id,))
        conn.commit()
        
        try:
            sender = EmailSender(
                email_job[1],  # smtp_server
                email_job[2],  # smtp_port
                email_job[3],  # smtp_username
                email_job[4]   # smtp_password
            )
            
            emails = email_job[8].split('\n')  # emails
            results = sender.send_bulk_emails(
                emails,
                email_job[5],  # subject
                email_job[6],  # body
                bool(email_job[7])  # is_html
            )
            
            success_count = sum(1 for r in results if r['success'])
            status = 'completed' if success_count == len(results) else 'partial'
            
            cursor.execute("UPDATE scheduled_emails SET status=? WHERE id=?", (status, email_id))
            conn.commit()
            
            print(f"Processed scheduled email {email_id}: {status} ({success_count}/{len(results)} successful)")
        except Exception as e:
            cursor.execute("UPDATE scheduled_emails SET status='failed' WHERE id=?", (email_id,))
            conn.commit()
            print(f"Failed to process scheduled email {email_id}: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/send', methods=['POST'])
def send_emails():
    data = request.form
    smtp_config = {
        'server': data.get('smtp_server'),
        'port': int(data.get('smtp_port')),
        'username': data.get('smtp_username'),
        'password': data.get('smtp_password')
    }
    
    subject = data.get('subject')
    body = data.get('body')
    is_html = data.get('is_html', 'false') == 'true'
    schedule_datetime = data.get('schedule_datetime')
    
    # Check if emails are provided via textarea or file
    emails = []
    if 'emails' in data and data['emails'].strip():
        emails = [email.strip() for email in data['emails'].split('\n') if email.strip()]
    
    if 'email_file' in request.files:
        file = request.files['email_file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            emails_from_file = read_emails_from_file(filepath)
            emails.extend(emails_from_file)
            os.remove(filepath)  # Clean up
    
    if not emails:
        return jsonify({'success': False, 'error': 'No valid email addresses provided'})
    
    # Validate SMTP configuration
    if not all(smtp_config.values()):
        return jsonify({'success': False, 'error': 'Invalid SMTP configuration'})
    
    # Handle scheduled emails
    if schedule_datetime:
        try:
            send_time = datetime.strptime(schedule_datetime, '%Y-%m-%d %H:%M')
            if send_time < datetime.now():
                return jsonify({'success': False, 'error': 'Scheduled time must be in the future'})
            
            # Store in database
            with sqlite3.connect(app.config['DATABASE']) as conn:
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO scheduled_emails 
                              (smtp_server, smtp_port, smtp_username, smtp_password,
                               subject, body, is_html, emails, send_time)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                              (smtp_config['server'], smtp_config['port'],
                               smtp_config['username'], smtp_config['password'],
                               subject, body, is_html, '\n'.join(emails),
                               send_time.strftime('%Y-%m-%d %H:%M:%S')))
                email_id = cursor.lastrowid
                conn.commit()
            
            # Schedule the job
            scheduler.add_job(
                process_scheduled_email,
                'date',
                run_date=send_time,
                args=[email_id],
                id=f'email_{email_id}'
            )
            
            return jsonify({
                'success': True,
                'message': f'Email scheduled successfully for {send_time.strftime("%Y-%m-%d %H:%M")}'
            })
        
        except ValueError as e:
            return jsonify({'success': False, 'error': f'Invalid datetime format: {str(e)}'})
        except Exception as e:
            return jsonify({'success': False, 'error': f'Scheduling failed: {str(e)}'})
    
    # Immediate sending
    def send_in_background():
        sender = EmailSender(
            smtp_config['server'],
            smtp_config['port'],
            smtp_config['username'],
            smtp_config['password']
        )
        results = sender.send_bulk_emails(emails, subject, body, is_html)
        
        # Log results
        success_count = sum(1 for r in results if r['success'])
        error_count = len(results) - success_count
        print(f"Sent {success_count} emails successfully, {error_count} failed")
    
    thread = threading.Thread(target=send_in_background)
    thread.start()
    
    return jsonify({
        'success': True,
        'message': f'Email sending process started for {len(emails)} recipients'
    })

@app.route('/scheduled', methods=['GET'])
def get_scheduled_emails():
    with sqlite3.connect(app.config['DATABASE']) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, subject, send_time, status FROM scheduled_emails ORDER BY send_time DESC")
        emails = cursor.fetchall()
    
    return jsonify({
        'success': True,
        'emails': [{
            'id': email[0],
            'subject': email[1],
            'send_time': email[2],
            'status': email[3]
        } for email in emails]
    })

if __name__ == '__main__':
    app.run(debug=True)