from pydantic import BaseModel


class OutboundRescheduleRequest(BaseModel):
    """
    Data modelling class that extends base model class,
    this class will handle the data we will receive from
    api
    """

    phone_number_to: str
    phone_number_from: str
    agent_id: str
    doctor_name: str
    message: str
    # patient_name: str
    # appointment_id: str
    first_name: str
    last_name: str
    date_of_birth: str
    # date: str
    old_start_date: str
    old_end_date: str


class OutboundPatientReviewRequest(BaseModel):
    """
    Data modelling class that extends base model class,
    this class will handle the data we will receive from
    api
    """

    phone_number_to: str
    phone_number_from: str
    message: str
    first_name: str
    last_name: str
    appointment_date: str
    checkup: str = None
    review: str = None
    agent_id: str
    doctor_name: str


class OutboundAppointmentConfirmationRequest(BaseModel):
    """
    Data modelling class that extends base model class,
    this class will handle the data we will receive from
    api
    """

    appointment_date: str
    doctor_name: str
    reason: str
    phone_number_from: str
    phone_number_to: str
    agent_id: str


class OutboundPatientOutreachRequest(BaseModel):
    """
    Data modelling class that extends base model class,
    this class will handle the data we will receive from
    api
    """

    phone_number_to: str
    phone_number_from: str
    first_name: str
    last_name: str
    date_of_birth: str
    message: str
    appointment_date: str
    reason: str
    doctor_name: str
    agent_id : str
    
class OutboundSMSAppointmentConfirmation(BaseModel):
    """
    Data modelling class that extends base model class,
    this class will handle the data we will receive from
    api
    """

    phone_number_from: str
    phone_number_to: str
    message: str
    appointment_id: str
    outbound_type: str = "APPOINTMENT_CONFIRMATION"