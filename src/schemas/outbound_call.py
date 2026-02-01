from pydantic import BaseModel


class OutboundRescheduleRequest(BaseModel):
    """
    Data modelling class that extends base model class,
    this class will handle the data we will receive from
    api
    """

    phone_number_to: str
    # agent_id: str
    # dr: str
    message: str
    # patient_name: str
    appointment_id: str
    date: str
