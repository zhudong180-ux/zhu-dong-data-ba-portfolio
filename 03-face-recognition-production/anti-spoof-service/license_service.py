import base64
import json
import os
import time
import urllib.parse
from application.main import celery_app
from conf.config import LicenseMode
from conf.config import license_store_dir, license_filepath, sm4_iv_filepath
from conf.config import serviceConf, ReturnCode
from conf.config import rsa_pub_key_filepath, rsa_priv_key_filepath
from libs import log
from libs.myutils import get_request_sequence_id
from libs.myutils import encrypt_xor, aes_iv, magic_num
from libs.redis_db import RedisDBWrapper
from libs.rsa_wrapper import RSAEncryption
from libs.sm4_wrapper import SM4Encryption

logger = log.get_logger("license-service")

_redis = RedisDBWrapper()

if not os.path.exists(license_store_dir):
    os.makedirs(license_store_dir)

#g_my_sm4 = SM4Encryption()

#max_api_calls_name = g_my_sm4.encrypt("max_api_calls", iv=aes_iv)

#invoke_cnt_name = g_my_sm4.encrypt("invoke_cnt", iv=aes_iv)
max_api_calls_name = "XXXXXXXXXXXXXXXXXXXX"

invoke_cnt_name = "YYYYYYYYYYYYYYYYYYYY"


def request_license(rqst_data, request_files):

    sequence_id = get_request_sequence_id("request_license_{}".format(os.getpid()))

    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "success": True,
        "data": "",
        "seqNo": sequence_id
    }

    try:
        req_mode = rqst_data.get('mode', None)
        if req_mode is None:
            raise Exception("Params[{}] is missing".format("mode"))

        if req_mode not in [LicenseMode.RSA.value, LicenseMode.SM4.value]:
            raise Exception("Params[{}] should be {} or {}".format("mode", LicenseMode.RSA.value, LicenseMode.SM4.value))

        if req_mode == LicenseMode.RSA.value:
            rsa = RSAEncryption()
            _, pub_key = rsa.generate_keys(1024)
            rsa.export_keys()

            pub_key = base64.b64encode(pub_key.export_key()).decode('utf-8')
            resp_info["data"] = pub_key

            logger.info("generate RSA pub key is {}".format(pub_key))
        else:
            my_sm4 = SM4Encryption()
            iv = my_sm4.generate_iv()
            logger.info("generated iv = {}".format(iv))

            iv = base64.b64encode(iv).decode('utf-8')
            resp_info["data"] = iv

            logger.info("generate SM4 iv is {}".format(iv))
    except Exception as e:
        logger.error("Fail to request license due to error: {}".format(e))

        resp_info["code"] = ReturnCode.REQUEST_LICENSE_ERROR.value
        resp_info["message"] = str(e)
        resp_info["success"] = False

    return resp_info


def import_license(rqst_data, request_files):
    sequence_id = get_request_sequence_id("import_license_{}".format(os.getpid()))

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
        enc_license_data = rqst_data.get('license', None)
        if enc_license_data is None:
            raise Exception("Params[{}] is missing".format("license"))

        enc_license_data = urllib.parse.unquote(enc_license_data)

        req_mode = rqst_data.get('mode', None)
        if req_mode is None:
            raise Exception("Params[{}] is missing".format("mode"))

        if req_mode not in [LicenseMode.RSA.value, LicenseMode.SM4.value]:
            raise Exception("Params[{}] should be {} or {}".format("mode", LicenseMode.RSA.value, LicenseMode.SM4.value))

        if req_mode == LicenseMode.RSA.value:
            rsa = RSAEncryption()

            priv_key = rsa.load_private_key()
            license_data = rsa.decrypt(enc_license_data, priv_key)
        else:
            my_sm4 = SM4Encryption()

            license_data = my_sm4.decrypt(enc_license_data)

        with open(license_filepath, 'w') as f:
            f.write(license_data)

        license_data = json.loads(license_data)

        _redis.get_handler().set(max_api_calls_name, encrypt_xor(license_data["max_api_calls"], magic_num))
        _redis.get_handler().set(invoke_cnt_name, encrypt_xor(1, magic_num))

        resp_info["data"] = license_data

        logger.info("succeed to import license: {}".format(license_data))

    except Exception as e:
        logger.error("Fail to import license due to error: {}".format(e))

        resp_info["code"] = ReturnCode.IMPORT_LICENSE_ERROR.value
        resp_info["message"] = str(e)
        resp_info["success"] = False
    finally:
        if os.path.exists(rsa_pub_key_filepath):
            os.remove(rsa_pub_key_filepath)

        if os.path.exists(rsa_priv_key_filepath):
            os.remove(rsa_priv_key_filepath)

        if os.path.exists(sm4_iv_filepath):
            os.remove(sm4_iv_filepath)

    return resp_info


def disable_license(rqst_data, request_files):

    sequence_id = get_request_sequence_id("disable_license_{}".format(os.getpid()))

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
        max_api_calls = _redis.get_handler().get(max_api_calls_name)
        if max_api_calls is None:
            raise Exception("max_api_calls is not set yet")

        _redis.get_handler().set(invoke_cnt_name, int(max_api_calls))

        if os.path.exists(license_filepath):
            os.remove(license_filepath)

        resp_info["data"] = "{} is deleted".format(license_filepath)
        logger.info("succeed to disable license")
    except Exception as e:
        logger.error("Fail to request license due to error: {}".format(e))

        resp_info["code"] = ReturnCode.DISABLE_LICENSE_ERROR.value
        resp_info["message"] = str(e)
        resp_info["success"] = False

    return resp_info


service_handler = {
    "req_license": request_license,
    "import_license": import_license,
    "disable_license": disable_license
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
