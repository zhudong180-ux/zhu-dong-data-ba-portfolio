import os
import time
import json
import magic
import tornado.web
from urllib.parse import unquote
from libs import log
from libs.myutils import make_md5
from application.main import celery_app
from libs.redis_db import RedisDBWrapper
from libs.milvus_db import MilvusDBWrapper
from conf.config import serviceConf, ReturnCode
from libs.myutils import get_request_sequence_id

logger = log.get_logger("file-service")

_redis = RedisDBWrapper()

vectorDB = MilvusDBWrapper()


def upload_files(rqst_data, request_files):
    sequence_id = get_request_sequence_id("receive_file_{}".format(os.getpid()))

    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "success": True,
        "data": "",
        "seqNo": sequence_id
    }

    global _redis
    if not _redis.check_connection():
        _redis = RedisDBWrapper()

    try:
        upload_files = request_files.get('data', None)
        if upload_files is None:
            raise Exception("data is empty!")

        for file in upload_files:
            m = magic.Magic()
            file_type_message = m.from_buffer(file['body'])

            logger.info("file meta type is : {}".format(file_type_message))

            file_type = file_type_message.split(' ')
            if not isinstance(file_type, list) or len(file_type) == 0:
                resp_info["code"] = ReturnCode.IMAGE_FORMAT_ERROR.value
                resp_info["message"] = "{} is not a valid image format".format(file_type_message)
                resp_info["success"] = False
                break

            if file_type[0].upper() not in ['JPEG', 'PNG', 'JPG', 'BMP', 'TIFF', 'GIF', 'RIFF']:
                resp_info["code"] = ReturnCode.IMAGE_FORMAT_ERROR.value
                resp_info["message"] = "{} is not a valid image format".format(file_type[0])
                resp_info["success"] = False
                break

            filename = file['filename']
            p = filename.rfind(os.sep)
            if p > 0:
                filename = filename[p + 1:]

            file_md5 = get_request_sequence_id(filename)
            target_filepath = os.path.join(serviceConf.IMAGE_ROOT_PATH, file_md5[-2:])
            target_filepath = os.path.join(target_filepath, "{}.{}".format(filename, file_md5))

            # p = target_filepath.rfind('.')
            # if p > 0:
            #     target_filepath = target_filepath[:p] + "_{}.{}".format(sequence_id, target_filepath[p + 1:])
            # else:
            #     target_filepath = target_filepath + "_{}".format(sequence_id)

            with open(target_filepath, 'wb') as f:
                f.write(file['body'])

            p = target_filepath.rfind(os.sep)

            resp_info["data"] = make_md5(target_filepath[p + 1:])

            _redis.get_handler().set(resp_info["data"], target_filepath)

            logger.info("image file is saved in {}, image_id is {}".format(target_filepath, resp_info["data"]))

    except Exception as e:
        logger.error("Fail to receive images due to error: {}".format(e))

        resp_info["code"] = ReturnCode.UPLOAD_IMAGE_ERROR.value
        resp_info["message"] = str(e)
        resp_info["success"] = False

    return resp_info


class DownloadHandler(tornado.web.RequestHandler):

    def initialize(self):
        self.response = '-'

    def get(self):

        rqst_data = dict(zip([x for x in list(self.request.arguments.keys())],
                             [x[0].decode() for x in list(self.request.arguments.values())]))

        image_name = None
        image_id = rqst_data.get('image_id', None)
        if image_id is None:
            image_name = rqst_data.get('image_name', None)
            if image_name is None:
                raise Exception("params[image_id] or params[image_name] is missing!")
            else:
                logger.info("download image_name: {}".format(image_name))
        else:
            logger.info("download image_id: {}".format(image_id))

        if not vectorDB.check_connection():
            vectorDB.reconnect()

        query_results = []

        if image_id is not None:
            query_results, err_message = vectorDB.query("image_id", [image_id])

            if len(err_message) > 0:
                raise Exception(err_message)

            if len(query_results) == 0:
                raise Exception("No image is found by: {}".format(image_id))

        elif image_name is not None:
            query_results, err_message = vectorDB.query("image_name", [image_name])

            if len(err_message) > 0:
                raise Exception(err_message)

            if len(query_results) == 0:
                raise Exception("No image is found by: {}".format(image_name))

        image_item = [{"image_id": q["image_id"], "image_name": q["image_name"], "image_path": q["image_path"]}
                      for q in query_results][0]

        self.set_header('Content-Type', 'application/octet-stream')
        self.set_header('Content-Disposition', 'attachment; filename=%s' % image_item["image_name"])

        target_filepath = image_item["image_path"]

        try:
            with open(target_filepath, 'rb') as f:
                while True:
                    data = f.read(1024)
                    if not data:
                        break
                    self.write(data)

        except Exception as e:
            logger.error("Fail to download images due to error: {}".format(e))

            sequence_id = get_request_sequence_id("receive_file_{}".format(os.getpid()))

            resp_info = {
                "code": ReturnCode.DOWNLOAD_IMAGE_ERROR.value,
                "message": str(e),
                "success": False,
                "seqNo": sequence_id
            }

            self.response = json.dumps(resp_info)
            self.write(self.response)
        finally:
            self.finish()

    def request_summary(self):
        # remote_ip - method[GET/POST] uri[-]
        return "{remote_ip}\t-\t{method}\t{uri}".format(
            remote_ip=self.request.remote_ip,
            method=self.request.method,
            uri=unquote(self.request.uri))


service_handler = {
    "upload_image": upload_files
}


@celery_app.task
def handle(service_id, rqst_data, request_files):
    start = time.time()
    logger.info("=== start celery task ===")

    resp_info = service_handler[service_id](rqst_data, request_files)

    end = time.time()
    logger.info("resp_info={resp_info}\ttime_cost={time_cost}".format(
        resp_info=json.dumps(resp_info, ensure_ascii=False),
        time_cost=end - start)
    )

    return resp_info
