user_data = {
    'patient_id': '',
    'patient_name': '',
    'patient_dob': '',
    'patient_number': '',
    'call_id': '',
    'user_id': '',
    'call_type': '',
    'success': False
}

def set_user_data(data):
    user_data['patient_id'] = data.get('id', '')
    user_data['patient_name'] = f"{data.get('first_name', '')} {data.get('last_name', '')}"
    user_data['patient_dob'] = data.get('date_of_birth', '')
    user_data['patient_number'] = data.get('phone_number', '')
    user_data['success'] = data.get('success', False)
    user_data['call_type'] = data.get('call_type', '')