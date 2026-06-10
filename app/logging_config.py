import os
import logging
import logging.config
import structlog
import boto3


def setup_logging():
    """
    Configure structured JSON logging.
    - Always logs to console
    - Optionally also ships logs to AWS CloudWatch via watchtower
    """
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "eu-west-1")
    log_group = os.getenv("CLOUDWATCH_LOG_GROUP", "/parcel-routing/api")

    handlers = ["default"]

    logging_handlers = {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    }

    if aws_key and aws_secret:
        logging_handlers["cloudwatch"] = {
            "class": "watchtower.CloudWatchLogHandler",
            "boto3_client": boto3.client("logs", region_name=aws_region),
            "log_group_name": log_group,
            "log_stream_name": "app",
            "create_log_group": True,
        }
        handlers.append("cloudwatch")

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.processors.JSONRenderer(),
            },
        },
        "handlers": logging_handlers,
        "loggers": {
            "": {
                "handlers": handlers,
                "level": "INFO",
            },
        },
    })

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger()
    if aws_key and aws_secret:
        logger.info("cloudwatch_logging_enabled", log_group=log_group, region=aws_region)
        logging.getLogger().info('{"event":"cloudwatch_test_message","status":"sent_to_root_logger"}')
    else:
        logger.info(
            "logging_mode",
            mode="stdout_only",
            note="Set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY to enable CloudWatch",
        )