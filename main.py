from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
import json
from datetime import datetime


APP = Flask(__name__)

with open('config.json', 'r') as config_file:
    config = json.load(config_file)


API_KEY = config['API_KEY']
BASE_URL = config['BASE_URL']
AGENT_LOGIN = config['AGENT_LOGIN']
USECASE_ID = config['USECASE_ID']

HEADERS = {
    'Content-Type': 'application/vnd.api+json',
    'X-Authorization': f'Token {API_KEY}'
}

def fetch_appointments(page_number=1, page_size=50):
    params = {
        'page[number]': page_number,
        'page[size]': page_size
    }
    response = requests.get(BASE_URL, headers=HEADERS, params=params)
    if not response.ok:
        print(f"Error fetching appointments: {response.status_code}")
        return [], 0, 0

    # Put response.json() in a var
    appointment_data = response.json().get('data', [])
    meta = response.json().get('meta', {})
    record_count = meta.get('record-count', 0)
    page_count = meta.get('page-count', 0)
    processed_appointments = []

    for appointment in appointment_data:

        st_parsed = datetime.fromisoformat(appointment['attributes']['start-time'][:-1])
        et_parsed = datetime.fromisoformat(appointment['attributes']['end-time'][:-1])

        appointment['attributes']['start-time'] = st_parsed
        appointment['attributes']['end-time'] = et_parsed
        appointment['attributes']['guest_url'] = appointment['attributes'].get('guest-default-url', 'URL Not Available')
        appointment['attributes']['agent_url'] = appointment['attributes'].get('agent-default-url', 'URL Not Available')

        processed_appointments.append(appointment)

    return processed_appointments, record_count, page_count


def check_conflict(start_time, end_time, appointments):
    for appointment in appointments:
        appt_start = appointment['attributes']['start-time']
        appt_end = appointment['attributes']['end-time']

        if start_time < appt_end and end_time > appt_start:
            return True  # Conflict found
        if start_time >= end_time:
            return True

    return False  # No conflict found


@APP.route('/')
def index():
    page_number = request.args.get('page', 1, type=int)
    page_size = request.args.get('size', 50, type=int)
    appointments, record_count, page_count = fetch_appointments(page_number, page_size)
    return render_template(
        'index.html',
        appointments=appointments,
        page_size=page_size,
        page_number=page_number,
        page_count=page_count
    )


@APP.route('/add', methods=['POST'])
def add_appointment():
    guest_name = request.form['guest_name']
    start_time = datetime.fromisoformat(request.form['start_time'])
    end_time = datetime.fromisoformat(request.form['end_time'])

    # Fetch all existing appointments to check for conflicts
    appointments, _, _ = fetch_appointments()
    if check_conflict(start_time, end_time, appointments):
        return jsonify({
            'status': 'error',
            'message': 'Time slot not available. Please choose a different time slot.'
        }), 409

    # Prepare data for creating the appointment
    data = {
        "data": {
            "type": "appointments",
            "attributes": {
                "meeting-point": True,
                "start-time": start_time.isoformat() + 'Z',
                "end-time": end_time.isoformat() + 'Z',
                "status": "SCHEDULED",
                "agent-login": AGENT_LOGIN,
                "usecase-id": USECASE_ID,
                "guest-display-name": guest_name,
                "agent-display-name": "Nate Brown"
            }
        }
    }

    # Send the creation request to the server
    response = requests.post(BASE_URL, headers=HEADERS, json=data)
    if response.status_code == 201:
        return redirect(url_for('index'))
    else:
        print(f"Error creating appointment: {response.status_code}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to create appointment.'
        }), 500


@APP.route('/update', methods=['POST'])
def change_appointment():
    appointment_id = request.form['appointment_id']
    guest_name = request.form['guest_name']
    start_time = datetime.fromisoformat(request.form['start_time'])
    end_time = datetime.fromisoformat(request.form['end_time'])

    # Fetch all appointments to check for conflicts
    appointments, _, _ = fetch_appointments()
    # Exclude the current appointment from conflict checking
    filtered_appointments = [appt for appt in appointments if appt['id'] != appointment_id]
    if check_conflict(start_time, end_time, filtered_appointments):
        return jsonify({
            'status': 'error',
            'message': 'Time slot conflict detected. Please choose a different time slot.'
        }), 409

    # Prepare data for updating the appointment
    data = {
        "data": {
            "id": appointment_id,
            "type": "appointments",
            "attributes": {
                "start-time": start_time.isoformat() + 'Z',
                "end-time": end_time.isoformat() + 'Z',
                "guest-display-name": guest_name
            }
        }
    }

    # Send update request to the server
    response = requests.patch(f"{BASE_URL}/{appointment_id}", headers=HEADERS, json=data)
    if response.status_code == 200:
        return redirect(url_for('index'))
    else:
        print(f"Error updating appointment: {response.status_code}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to update appointment.'
        }), 500


@APP.route('/delete/<int:appointment_id>', methods=['POST'])
def delete_appointment_route(appointment_id):
    """
       Deletes an appointment based on its ID. Returns True if successful, False otherwise.
    """
    url = f"{BASE_URL}/{appointment_id}"

    response = requests.delete(url, headers=HEADERS)
    if not response.status_code == 204:  # HTTP 204 No Content: The server successfully processed the request.
        return jsonify({'error': 'Failed to delete appointment'}), 500

    return jsonify({'message': 'Appointment successfully deleted'})



if __name__ == '__main__':
    APP.run(debug=True)