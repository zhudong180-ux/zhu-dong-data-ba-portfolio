import datetime
import argparse
from libs import log
from libs.redis_db import RedisDBWrapper
from libs.myutils import get_request_sequence_id
from conf.config import ServiceMessageKey, ReturnCode, serviceConf
from models.anti_spoof_model import AntiSpoofModel
from models.insightface_model import InsightFaceModel

logger = log.get_logger("anti-spoof-service")

faceModel = InsightFaceModel()

antiSpoofModel = AntiSpoofModel()

_redis = RedisDBWrapper()


def _execute(inst_id):
    logger.info("start anti spoof face daemon")

    while True:
        resp_info = {
            "code": ReturnCode.SUCCESS_CODE.value,
            "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
            "data": {
                "status": "success"
            },
            "instance_id": inst_id,
            "seqNo": get_request_sequence_id("detect_spoof_face"),
            "datetime": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        message_uid = None

        try:
            message = _redis.pop_data(ServiceMessageKey.ANTI_SPOOF_FACE_MESSAGE_KEY.value, True)
            logger.info(message)

            if "data" not in message:
                raise Exception("data is missing in message")

            if "uid" not in message:
                raise Exception("uid is missing for response endpoint")

            use_multiple_faces = False
            if "use_multiple_faces" in message:
                use_multiple_faces = message["use_multiple_faces"]

            message_uid = message["uid"]
            image_items = message["data"]

            faceModel.setup(image_items)

            if use_multiple_faces:
                valid_image_features, invalid_image_features = faceModel.extract_multiple_faces()
            else:
                valid_image_features, invalid_image_features = faceModel.extract()

            if len(invalid_image_features) > 0:
                err_msg = ""
                for invalid_info in invalid_image_features:
                    err_msg = err_msg + "image: {} failed to detect face due to {}; ".format(
                        invalid_info["image_name"], invalid_info["error_info"])

                raise Exception(err_msg)

            antiSpoofModel.setup(valid_image_features)

            if use_multiple_faces:
                result_items, err_items = antiSpoofModel.detect_multi_faces()
            else:
                result_items, err_items = antiSpoofModel.detect_single_face()

            if len(err_items) > 0:
                raise Exception(err_items)
            else:
                resp_info["data"]["image_list"] = result_items

            logger.info("inst_id[]: {}".format(inst_id, resp_info))

        except Exception as e:
            logger.error("inst_id[]: fail to detect spoof face due to {}".format(inst_id, e))

            resp_info["code"] = ReturnCode.ANTI_SPOOF_IMAGE_ERROR.value
            resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.ANTI_SPOOF_IMAGE_ERROR]
            resp_info["data"]["status"] = str(e)
        finally:
            if message_uid is not None:
                if _redis.push_data(resp_info, message_uid) < 0:
                    logger.error("Fail to push data to redis queue: {}".format(message_uid))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="anti spoof face service")

    parser.add_argument(
        "--inst_id",
        type=str,
        default=1,
        help="service instance id")
    args = parser.parse_args()

    _execute(args.inst_id)


