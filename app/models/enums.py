import enum


class AppointmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    RESCHEDULED = "RESCHEDULED"


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    RECEPTIONIST = "RECEPTIONIST"
    DOCTOR = "DOCTOR"


class BookingType(str, enum.Enum):
    AUTO_CONFIRM = "AUTO_CONFIRM"
    MANUAL_APPROVAL = "MANUAL_APPROVAL"


class MessageDirection(str, enum.Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class ReminderType(str, enum.Enum):
    HOURS_24 = "HOURS_24"
    HOURS_2 = "HOURS_2"


class ReminderStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
