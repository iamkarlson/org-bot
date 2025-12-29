import json
import logging


class GCPLogger(logging.getLoggerClass()):
    def __init__(self, name, project=None, request=None):
        super().__init__(name)
        self.project = project
        self.request = request
        self.global_log_fields = {}

        if request:
            trace_header = request.headers.get("X-Cloud-Trace-Context")
            if trace_header and project:
                trace = trace_header.split("/")
                self.global_log_fields["logging.googleapis.com/trace"] = (
                    f"projects/{project}/traces/{trace[0]}"
                )

    def _log_structured(self, severity, msg, args, kwargs):
        if args:
            msg = msg % args
        extra = kwargs.pop("extra", None)
        entry = {
            "severity": severity,
            "message": msg,
            "logger_name": self.name,
            **self.global_log_fields,
        }

        if extra:
            entry["jsonPayload"] = extra

        print(json.dumps(entry))

    def debug(self, msg, *args, **kwargs):
        self._log_structured("DEBUG", msg, args, kwargs)

    def info(self, msg, *args, **kwargs):
        self._log_structured("INFO", msg, args, kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log_structured("WARNING", msg, args, kwargs)

    def error(self, msg, *args, **kwargs):
        self._log_structured("ERROR", msg, args, kwargs)


if __name__ == "__main__":
    # Set the new logger class
    logging.setLoggerClass(GCPLogger)

    # Create a logger instance
    logger = logging.getLogger(__name__)

    # Usage
    logger.warning("File path is not provided. Using default file path.")
    logger.error("Token is not provided.", extra={"token_status": "missing"})
    logger.info("Added to journal!", extra={"action": "add_to_journal"})
    logger.debug('{"key": "value"}')
