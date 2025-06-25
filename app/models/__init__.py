# Módulo models: define las clases y estructuras de datos principales de la aplicación (SQLModel/Pydantic)
# El orden de las importaciones es importante para la creación de las tablas en la base de datos
# Las tablas se crean en el orden en que se importan sus modelos
# Las tablas con claves foráneas deben importarse después de las tablas que referencian

from .role import Role
from .user_has_roles import UserHasRole
from .document_type import DocumentType
from .driver import DriverCreate
from .driver_info import DriverInfo, DriverInfoBase
from .vehicle_info import VehicleInfo, VehicleInfoCreate, VehicleInfoUpdate
from .vehicle_type import VehicleType, VehicleTypeCreate, VehicleTypeUpdate
from .user import User, UserCreate, UserUpdate, UserRead
from .driver_documents import DriverDocuments, DriverDocumentsCreate, DriverDocumentsUpdate
from .payment_method import PaymentMethod
from .client_request import ClientRequest, ClientRequestCreate
from .driver_position import DriverPosition
from .driver_trip_offer import DriverTripOfferCreate, DriverTripOffer
from .project_settings import ProjectSettings
from .referral_chain import Referral
from .company_account import CompanyAccount
from .driver_savings import DriverSavings
from .transaction import Transaction, TransactionType
from .verify_mount import VerifyMount
from .type_service import TypeService, TypeServiceCreate, TypeServiceRead
from .config_service_value import ConfigServiceValue, VehicleTypeConfigurationCreate, VehicleTypeConfigurationUpdate, VehicleTypeConfigurationResponse
from .withdrawal import Withdrawal, WithdrawalStatus
from .penality_user import PenalityUser, statusEnum
from .refresh_token import RefreshToken
