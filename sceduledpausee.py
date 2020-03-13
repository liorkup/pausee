import logging
from pausee import pausee
import schedule
import time
import yaml
import functools
import traceback


def catch_exceptions(cancel_on_failure=False):
    def catch_exceptions_decorator(job_func):
        @functools.wraps(job_func)
        def wrapper(*args, **kwargs):
            try:
                return job_func(*args, **kwargs)
            except:
                logging.error(traceback.format_exc())
                if cancel_on_failure:
                    return schedule.CancelJob

        return wrapper

    return catch_exceptions_decorator


@catch_exceptions()
def pausee_job():
    pausee()


def main():
    with open('config.yaml', 'r') as stream:
        try:
            cfg = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logging.info(exc)

    repeat_min = cfg['params']['repeat']
    logging.info('Pausee scheduled to run every {} minutes.'.format(repeat_min))

    # Run now
    pausee_job()

    # Run every repeat_min
    schedule.every(repeat_min).minutes.do(pausee_job)
    while True:
        schedule.run_pending()
        time.sleep(1)


def setup_logs():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers={
            logging.FileHandler("pausee.log"),
            logging.StreamHandler()
        }
    )


if __name__ == '__main__':
    setup_logs()
    main()
