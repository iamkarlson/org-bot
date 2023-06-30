from commands.start import command_start
from commands.webhook import command_webhook
from commands.info import command_info

commands = {
    "/start": command_start,
    "/webhook": command_webhook,
    "/info": command_info,
}
