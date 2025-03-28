# Bulk-Schedule-email

# Bulk Schedule Email

## Project Description:
Bulk Schedule Email is a Python-based web application that allows users to send bulk emails to multiple recipients with scheduled delivery times. The app uses Flask as the web framework and integrates with email services to send emails asynchronously. It’s designed to help users automate the process of sending bulk emails, whether for marketing, reminders, or other purposes, with the added benefit of scheduling email delivery at specified times.

## Features:
- **Bulk Email Sending**: Send personalized emails to multiple recipients.
- **Scheduled Email Delivery**: Set a date and time for email delivery.
- **CSV File Upload**: Import email addresses and recipient data from CSV files.
- **Simple Web Interface**: Built with Flask for a minimal and easy-to-use UI.
- **Database Support**: Store email logs and scheduled emails in a SQLite database.
- **Customizable Email Templates**: Use HTML templates to customize email content.
- **Real-Time Feedback**: View the status of each email in real-time (sent, failed, pending).

## Tech Stack:
- **Backend**: Python, Flask
- **Frontend**: HTML (using Flask templates)
- **Database**: SQLite
- **Email Service**: SMTP (e.g., Gmail, SendGrid, or any other email service)
- **Scheduling**: Celery (or similar task queue) for scheduling emails

## Installation Instructions:
1. **Clone the repository**:
   ```bash
   git clone https://github.com/purushothamCN/Bulk-Schedule-email.git
   cd Bulk-Schedule-email
