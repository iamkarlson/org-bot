from .start import command_start
from .webhook import command_webhook
from .info import command_info

commands = {
    "/start": command_start,
    "/webhook": command_webhook,
    "/info": command_info,
}
