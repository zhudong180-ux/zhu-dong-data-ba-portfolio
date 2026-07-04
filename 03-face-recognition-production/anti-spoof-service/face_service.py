import os
import re
import time
import json
import magic
import random
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
## import pyiqa
#import torch
#import cv2
from libs import log
from libs.myutils import encrypt_xor, decrypt_xor, aes_iv, magic_num
from libs.myutils import check_number, get_request_sequence_id, make_md5, get_face_area, decode_base64_url_to_image
from application.main import celery_app
from libs.milvus_db import MilvusDBWrapper
from models.insightface_model import InsightFaceModel
from models.cv2dnn_model import CV2DNNModel
from libs.redis_db import RedisDBWrapper
from libs.score_converter import EuclideanDistanceScoreModel, CosineSimilarityScoreModel
from libs.face_quality_scorer import FaceQualityScoreModel, FaceQualityThresholdModel
from conf.model_config import InsightFaceConf, DlibConf, CV2DNNConf, ModelFramework
from conf.config import serviceConf, ReturnCode, ServiceMessageKey
from models.mask_model import MaskModel
from libs.sm4_wrapper import SM4Encryption

faceModel = InsightFaceModel()

optionalFaceModel = CV2DNNModel()

maskFaceModel = MaskModel()

vectorDB = MilvusDBWrapper()

logger = log.get_logger("face-service")

_redis = RedisDBWrapper()

_euclideanDistance2Score = EuclideanDistanceScoreModel()

_euclideanDistance2Score.build()

_default_search_score = _euclideanDistance2Score.convert_distance(serviceConf.SCORE_THRESHOLD)

_cosineSimilarity2Score = CosineSimilarityScoreModel()

_cosineSimilarity2Score.build()

# 初始化人脸质量评分模型
_faceQualityScorer = FaceQualityScoreModel()
_faceQualityThreshold = FaceQualityThresholdModel()

deploy_for_evaluation = False

#my_sm4 = SM4Encryption()

# 初始化质量检测模型
# try:
#     quality_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#     quality_assessor = pyiqa.create_metric('brisque', device=quality_device)
#     logger.info(f"质量检测模型初始化成功，使用设备: {quality_device}")
# except Exception as e:
#     quality_assessor = None
#     logger.error(f"质量检测模型初始化失败: {str(e)}")

#max_api_calls_name = my_sm4.encrypt("max_api_calls", iv=aes_iv)

#invoke_cnt_name = my_sm4.encrypt("invoke_cnt", iv=aes_iv)

max_api_calls_name = "XXXXXXXXXXXXXXXXXXXX"

invoke_cnt_name = "YYYYYYYYYYYYYYYYYYYY"

max_api_calls = _redis.get_handler().get(max_api_calls_name)
if max_api_calls is None:
    max_api_calls = encrypt_xor(100, magic_num)
    _redis.get_handler().set(max_api_calls_name, max_api_calls)


def _get_compare_face_result(image_items, model_framework):
    global faceModel, optionalFaceModel

    if model_framework == ModelFramework.INSIGHT_FACE:
        face_model = faceModel
    elif model_framework == ModelFramework.DLIB or model_framework == ModelFramework.CV2DNN_DLIB:
        face_model = optionalFaceModel
    else:
        raise Exception("Face model only support insightFace or Dlib or cv2dnn ")

    face_model.setup(image_items)

    valid_image_features, invalid_image_features = face_model.extract()

    if len(invalid_image_features) > 0:
        return -1, -1, invalid_image_features

    # 这里当一张照片有多张人脸，取面积最大的那张人脸
    max_face1_idx = valid_image_features[0]["max_face_idx"]
    max_face2_idx = valid_image_features[1]["max_face_idx"]

    face_vec1 = valid_image_features[0]["face_vectors"][max_face1_idx]
    face_vec2 = valid_image_features[1]["face_vectors"][max_face2_idx]

    euclidean_distance = float(np.linalg.norm(face_vec1 - face_vec2, ord=2))
    cosine_similarity_value = float(cosine_similarity(face_vec1.reshape(1, -1), face_vec2.reshape(1, -1))[0][0])

    del valid_image_features

    if model_framework == ModelFramework.DLIB:
        cosine_similarity_value = InsightFaceConf.cosine_similarity_threshold / DlibConf.cosine_similarity_threshold * cosine_similarity_value
        euclidean_distance = InsightFaceConf.euclidean_distance_threshold / DlibConf.euclidean_distance_threshold * euclidean_distance
    elif model_framework == ModelFramework.CV2DNN_DLIB:
        cosine_similarity_value = InsightFaceConf.cosine_similarity_threshold / CV2DNNConf.cosine_similarity_threshold * cosine_similarity_value
        euclidean_distance = InsightFaceConf.euclidean_distance_threshold / CV2DNNConf.euclidean_distance_threshold * euclidean_distance

    return euclidean_distance, cosine_similarity_value, invalid_image_features


def _extract_image_data(request_files, need_all=False):
    upload_files = request_files.get('image', None)
    if upload_files is None:
        raise Exception("image data is empty!")

    image_filepath_list = []

    for file in upload_files:
        m = magic.Magic()
        file_type_message = m.from_buffer(file['body'])

        logger.info("file meta type is : {}".format(file_type_message))

        file_type = file_type_message.split(' ')
        if not isinstance(file_type, list) or len(file_type) == 0:
            raise Exception("{} is not a valid image format".format(file_type_message))

        if file_type[0].upper() not in ['JPEG', 'PNG', 'JPG', 'BMP', 'TIFF', 'GIF', 'RIFF']:
            raise Exception("{} is not a valid image format".format(file_type_message))

        filename = file['filename']
        p = filename.rfind(os.sep)
        if p > 0:
            filename = filename[p + 1:]

        file_md5 = get_request_sequence_id(filename)

        target_filepath = os.path.join(serviceConf.IMAGE_ROOT_PATH, file_md5[-2:])
        target_filepath = os.path.join(target_filepath, "{}.{}".format(filename, file_md5))

        with open(target_filepath, 'wb') as f:
            f.write(file['body'])

        image_filepath_list.append(target_filepath)
        if not need_all:
            break

    return image_filepath_list

def _parse_image_items_from_image_id(rqst_data):
    image_id_list = rqst_data.get('image_id_list', None)
    if image_id_list is not None:
        image_id_list = image_id_list.split(',')
        image_id_list = [x.strip() for x in image_id_list]

        if not vectorDB.check_connection():
            vectorDB.reconnect()

        query_results, err_message = vectorDB.query("image_id", image_id_list)
    else:
        image_name_list = rqst_data.get('image_name_list', None)
        if image_name_list is None:
            raise Exception("Params[{}] or Params[{}] is missing".format("image_id_list", "image_name_list"))

        image_name_list = image_name_list.split(',')
        image_name_list = [x.strip() for x in image_name_list]

        if not vectorDB.check_connection():
            vectorDB.reconnect()

        query_results, err_message = vectorDB.query("image_name", image_name_list)

    if len(err_message) > 0:
        raise Exception(err_message)

    image_items = [{"image_id": q["image_id"], "image_name": q["image_name"], "image_path": q["image_path"]}
                   for q in query_results]

    return image_items


def _parse_image_items_from_image_url(rqst_data):
    encoded_image_data_list = rqst_data.get('image_data_list', None)
    if encoded_image_data_list is None:
        raise Exception("Params[{}] is missing".format("image_data_list"))

    encoded_image_data_list = encoded_image_data_list.split('&')

    image_items = []

    for encoded_image_data in encoded_image_data_list:

        filename = make_md5(encoded_image_data)

        target_filepath = os.path.join(serviceConf.IMAGE_ROOT_PATH, filename[-2:])
        target_filepath = os.path.join(target_filepath, filename)

        decode_base64_url_to_image(encoded_image_data, target_filepath)

        image_items.append({"image_id": make_md5(filename), "image_name": filename, "image_path": target_filepath})

    return image_items


def _parse_use_multiple_faces(rqst_data):
    use_multiple_faces = rqst_data.get('use_multiple_faces', None)

    if use_multiple_faces is not None:
        if isinstance(use_multiple_faces, str):
            use_multiple_faces = use_multiple_faces.strip()
            if use_multiple_faces in ["True", "TRUE", "true"]:
                use_multiple_faces = True
            elif use_multiple_faces in ["False", "FALSE", "false"]:
                use_multiple_faces = False
            else:
                raise Exception("Params[{use_multiple_faces}] is not a boolean value")

        if not isinstance(use_multiple_faces, bool):
            raise Exception("Params[{use_multiple_faces}] is not a boolean value")
    else:
        use_multiple_faces = False

    return use_multiple_faces


def compare_faces(rqst_data, request_files):
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success",
            "score": -1,
        },
        "seqNo": get_request_sequence_id("compare_faces")
    }

    try:
        image_path_list = _extract_image_data(request_files, True)
        if len(image_path_list) == 0:
            raise Exception("Fail to find image data")

        if len(image_path_list) == 1:
            raise Exception("only find one image")

        p = image_path_list[0].rfind(os.sep)
        q = image_path_list[0].rfind('.')
        image_name1 = image_path_list[0][p + 1: q]
        image_id1 = image_path_list[0][q + 1:]

        p = image_path_list[1].rfind(os.sep)
        q = image_path_list[1].rfind('.')
        image_name2 = image_path_list[1][p + 1: q]
        image_id2 = image_path_list[1][q + 1:]

        image_items = [{"image_id": image_id1, "image_name": image_name1, "image_path": image_path_list[0]},
                       {"image_id": image_id2, "image_name": image_name2, "image_path": image_path_list[1]}]

        euclidean_distance, cosine_similarity_value, invalid_image_features = _get_compare_face_result(image_items,
                                                                                                       ModelFramework.INSIGHT_FACE)
        if len(invalid_image_features) > 0 or \
                (
                        InsightFaceConf.euclidean_distance_threshold <= euclidean_distance < InsightFaceConf.euclidean_distance_threshold * serviceConf.euclidean_distance_adjust_ptg and \
                        InsightFaceConf.cosine_similarity_threshold >= cosine_similarity_value > InsightFaceConf.cosine_similarity_threshold * serviceConf.cosine_similarity_adjust_ptg):
            euclidean_distance, cosine_similarity_value, invalid_image_features = _get_compare_face_result(image_items,
                                                                                                           ModelFramework.CV2DNN_DLIB)

        if len(invalid_image_features) == 0:
            score = _euclideanDistance2Score.convert_score(euclidean_distance)

            if euclidean_distance >= InsightFaceConf.euclidean_distance_threshold and \
                    cosine_similarity_value > InsightFaceConf.cosine_similarity_threshold:
                score = _cosineSimilarity2Score.convert_score(cosine_similarity_value)

            resp_info["data"]["score"] = score
        else:
            err_msg = ""
            for i, invalid_info in enumerate(invalid_image_features):
                err_msg = err_msg + "image id: {} failed to extract features due to {}; ".format(
                    invalid_info["image_id"],
                    invalid_info["error_info"])
            raise Exception(err_msg)

    except Exception as e:
        logger.error("Fail to compare images due to error: {}".format(e))
        resp_info["code"] = ReturnCode.COMPARE_FACE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.COMPARE_FACE_ERROR]

        resp_info["data"]["status"] = str(e)

    return resp_info


def compare_faces_by_image_id(rqst_data, request_files):
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success",
            "score": -1,
        },
        "seqNo": get_request_sequence_id("compare_faces_by_image_id")
    }

    try:
        image_id_1 = rqst_data.get('image_id_1', None)
        if image_id_1 is None:
            raise Exception("The parameter[image_id_1] is missing")

        image_id_2 = rqst_data.get('image_id_2', None)
        if image_id_2 is None:
            raise Exception("The parameter[image_id_2] is missing")

        image_id_list = [image_id_1, image_id_2]

        if not vectorDB.check_connection():
            vectorDB.reconnect()

        results, err_message = vectorDB.query("image_id", image_id_list, True)
        if len(results) == 0:
            raise Exception("No image can be retrieved")

        result_df = pd.DataFrame(results)
        if result_df[result_df.image_id == image_id_1].shape[0] == 0:
            raise Exception("The image id of '{}' cannot be retrieved".format(image_id_1))

        if result_df[result_df.image_id == image_id_2].shape[0] == 0:
            raise Exception("The image id of '{}' cannot be retrieved".format(image_id_2))

        result_df["face_area"] = result_df.face_box.apply(lambda x: get_face_area(x))
        max_face_df = result_df.groupby('image_id')["face_area"].max().to_frame().reset_index()
        result_df = pd.merge(result_df, max_face_df, on=["image_id", "face_area"])

        face_vec1 = np.array(result_df[result_df.image_id == image_id_1].face_vector.values[0])
        face_vec2 = np.array(result_df[result_df.image_id == image_id_2].face_vector.values[0])

        euclidean_distance = float(np.linalg.norm(face_vec1 - face_vec2, ord=2))
        cosine_similarity_value = float(cosine_similarity(face_vec1.reshape(1, -1), face_vec2.reshape(1, -1))[0][0])

        score = _euclideanDistance2Score.convert_score(euclidean_distance)

        if euclidean_distance >= InsightFaceConf.euclidean_distance_threshold and \
                cosine_similarity_value > InsightFaceConf.cosine_similarity_threshold:
            score = _cosineSimilarity2Score.convert_score(cosine_similarity_value)

        resp_info["data"]["score"] = score

    except Exception as e:
        logger.error("Fail to compare images due to error: {}".format(e))
        resp_info["code"] = ReturnCode.COMPARE_FACE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.COMPARE_FACE_ERROR]

        resp_info["data"]["status"] = str(e)

    return resp_info


def single_upload_face(rqst_data, request_files):
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success",
            "image_items": []
        },
        "seqNo": get_request_sequence_id("single_upload_face")
    }

    try:
        image_path_list = _extract_image_data(request_files)
        if len(image_path_list) == 0:
            raise Exception("Fail to find image data")

        image_path = image_path_list[0]

        p = image_path.rfind(os.sep)
        q = image_path.rfind('.')
        image_name = image_path[p + 1: q]
        image_id = image_path[q + 1:]

        use_multiple_faces = _parse_use_multiple_faces(rqst_data)

        use_upsert = rqst_data.get('use_upsert', None)
        if use_upsert is not None:
            if isinstance(use_upsert, str):
                use_upsert = use_upsert.strip()
                if use_upsert in ["True", "TRUE", "true"]:
                    use_upsert = True
                elif use_upsert in ["False", "FALSE", "false"]:
                    use_upsert = False
                else:
                    raise Exception("Params[{use_upsert}] is not a boolean value")

            if not isinstance(use_upsert, bool):
                raise Exception("Params[{use_upsert}] is not a boolean value")
        else:
            use_upsert = False

        image_items = [{"image_id": image_id, "image_name": image_name, "image_path": image_path}]

        faceModel.setup(image_items)

        if use_multiple_faces:
            valid_image_features, invalid_image_features = faceModel.extract_multiple_faces()
        else:
            valid_image_features, invalid_image_features = faceModel.extract()

        if len(invalid_image_features) > 0:
            raise Exception("image id: {} failed to upload due to {}; ". \
                            format(invalid_image_features[0]["image_id"], invalid_image_features[0]["error_info"]))

        if not vectorDB.check_connection():
            vectorDB.reconnect()

        ret, err_message = vectorDB.insert(valid_image_features, use_upsert=use_upsert)

        del valid_image_features
        del invalid_image_features

        if not ret:
            raise Exception(err_message)

        resp_info["data"]["image_items"] = image_items
    except Exception as e:
        logger.error("Fail to upload single image due to error: {}".format(e))
        resp_info["code"] = ReturnCode.UPLOAD_SINGLE_FACE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.UPLOAD_SINGLE_FACE_ERROR]

        resp_info["data"]["status"] = str(e)

    return resp_info


def batch_upload_face(rqst_data, request_files):
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success",
            "image_items": []
        },
        "seqNo": get_request_sequence_id("batch_upload_face")
    }

    try:
        image_path_list = _extract_image_data(request_files, True)
        if len(image_path_list) == 0:
            raise Exception("Fail to find image data")

        image_items = []
        for i, image_path in enumerate(image_path_list):
            p = image_path.rfind(os.sep)
            q = image_path.rfind('.')
            image_name = image_path[p + 1: q]
            image_id = image_path[q + 1:]

            image_items.append({"image_id": image_id, "image_name": image_name, "image_path": image_path})

        use_multiple_faces = _parse_use_multiple_faces(rqst_data)

        use_upsert = rqst_data.get('use_upsert', None)
        if use_upsert is not None:
            if isinstance(use_upsert, str):
                use_upsert = use_upsert.strip()
                if use_upsert in ["True", "TRUE", "true"]:
                    use_upsert = True
                elif use_upsert in ["False", "FALSE", "false"]:
                    use_upsert = False
                else:
                    raise Exception("Params[{use_upsert}] is not a boolean value")

            if not isinstance(use_upsert, bool):
                raise Exception("Params[{use_upsert}] is not a boolean value")
        else:
            use_upsert = False

        faceModel.setup(image_items)

        if use_multiple_faces:
            valid_image_features, invalid_image_features = faceModel.extract_multiple_faces()
        else:
            valid_image_features, invalid_image_features = faceModel.extract()

        if len(invalid_image_features) > 0:
            err_msg = ""
            for invalid_info in invalid_image_features:
                err_msg = err_msg + "image: {} failed to upload batch images due to {}; ".format(
                    invalid_info["image_name"], invalid_info["error_info"])

            raise Exception(err_msg)

        if not vectorDB.check_connection():
            vectorDB.reconnect()

        ret, err_message = vectorDB.insert(valid_image_features, use_upsert=use_upsert)

        del valid_image_features
        del invalid_image_features

        if ret:
            resp_info["data"]["status"] = "success"
            resp_info["data"]["image_items"] = image_items
        else:
            raise Exception(err_message)
    except Exception as e:
        logger.error("Fail to upload batch images due to error: {}".format(e))
        resp_info["code"] = ReturnCode.UPLOAD_MULTIPLE_FACE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.UPLOAD_MULTIPLE_FACE_ERROR]

        resp_info["data"]["status"] = str(e)

    return resp_info


def search_face(rqst_data, request_files):
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success",
            "image_list": {}
        },
        "seqNo": get_request_sequence_id("search_face")
    }

    try:
        image_path_list = _extract_image_data(request_files)
        if len(image_path_list) == 0:
            raise Exception("Fail to find image data")

        image_path = image_path_list[0]

        p = image_path.rfind(os.sep)
        q = image_path.rfind('.')
        image_name = image_path[p + 1: q]

        image_id = rqst_data.get('image_id', None)
        if image_id is None:
            image_id = image_path[q + 1:]

        use_multiple_faces = _parse_use_multiple_faces(rqst_data)

        exclude_identical_faces = rqst_data.get('exclude_identical_faces', None)

        search_score = rqst_data.get('search_score', None)
        if search_score is None:
            search_radius = serviceConf.SEARCH_REDIUS
        elif not check_number(search_score):
            raise Exception("Params[{}] is not a valid score number".format("search_score"))
        else:
            search_score = float(search_score)
            if search_score <= 0 or search_score > 1:
                raise Exception("Params[{}] must be in range of (0, 1]".format("search_score"))

            search_radius = _euclideanDistance2Score.convert_distance(search_score)
            logger.info("Convert score: {} to distance: {}".format(search_score, search_radius))

        if exclude_identical_faces is not None:
            if isinstance(exclude_identical_faces, str):
                exclude_identical_faces = exclude_identical_faces.strip()
                if exclude_identical_faces in ["True", "TRUE", "true"]:
                    exclude_identical_faces = True
                elif exclude_identical_faces in ["False", "FALSE", "false"]:
                    exclude_identical_faces = False
                else:
                    raise Exception("Params[{exclude_identical_faces}] is not a boolean value")

            if not isinstance(exclude_identical_faces, bool):
                raise Exception("Params[{exclude_identical_faces}] is not a boolean value")
        else:
            exclude_identical_faces = False

        image_items = [{"image_id": image_id, "image_name": image_name, "image_path": image_path}]

        faceModel.setup(image_items)

        if use_multiple_faces:
            valid_image_features, invalid_image_features = faceModel.extract_multiple_faces()
        else:
            valid_image_features, invalid_image_features = faceModel.extract()

        if len(invalid_image_features) > 0:
            raise Exception("image id: {} failed to search due to {}; ".format(
                invalid_image_features[0]["image_id"],
                invalid_image_features[0]["error_info"]))

        if not vectorDB.check_connection():
            vectorDB.reconnect()

        if use_multiple_faces:
            results, err_message = vectorDB.search_multiple_faces(valid_image_features, search_radius,
                                                                  exclude_identical_faces)
        else:
            results, err_message = vectorDB.search(valid_image_features, search_radius, exclude_identical_faces)

        del valid_image_features
        del invalid_image_features

        if len(err_message) > 0:
            raise Exception(err_message)
        else:
            resp_info["data"]["image_list"] = results
    except Exception as e:
        logger.error("Fail to search images due to error: {}".format(e))
        resp_info["code"] = ReturnCode.SEARCH_FACE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.SEARCH_FACE_ERROR]

        resp_info["data"]["status"] = str(e)

    return resp_info


def search_face_by_image_id(rqst_data, request_files):
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success",
            "image_list": {}
        },
        "seqNo": get_request_sequence_id("search_face_by_image_id")
    }

    try:
        image_id = rqst_data.get('image_id', None)
        if image_id is None:
            raise Exception("image_id is missing in parameters")

        use_multiple_faces = _parse_use_multiple_faces(rqst_data)

        exclude_identical_faces = rqst_data.get('exclude_identical_faces', None)

        search_score = rqst_data.get('search_score', None)
        if search_score is None:
            search_radius = serviceConf.SEARCH_REDIUS
        elif not check_number(search_score):
            raise Exception("Params[{}] is not a valid score number".format("search_score"))
        else:
            search_score = float(search_score)
            if search_score <= 0 or search_score > 1:
                raise Exception("Params[{}] must be in range of (0, 1]".format("search_score"))

            search_radius = _euclideanDistance2Score.convert_distance(search_score)
            logger.info("Convert score: {} to distance: {}".format(search_score, search_radius))

        if exclude_identical_faces is not None:
            if isinstance(exclude_identical_faces, str):
                exclude_identical_faces = exclude_identical_faces.strip()
                if exclude_identical_faces in ["True", "TRUE", "true"]:
                    exclude_identical_faces = True
                elif exclude_identical_faces in ["False", "FALSE", "false"]:
                    exclude_identical_faces = False
                else:
                    raise Exception("Params[{exclude_identical_faces}] is not a boolean value")

            if not isinstance(exclude_identical_faces, bool):
                raise Exception("Params[{exclude_identical_faces}] is not a boolean value")
        else:
            exclude_identical_faces = False

        if not vectorDB.check_connection():
            vectorDB.reconnect()

        if use_multiple_faces:
            results, err_message = vectorDB.search_multiple_faces_by_image_id(image_id, search_radius,
                                                                              exclude_identical_faces)
        else:
            results, err_message = vectorDB.search_by_image_id(image_id, search_radius, exclude_identical_faces)

        if len(err_message) > 0:
            raise Exception(err_message)
        else:
            resp_info["data"]["image_list"] = results
    except Exception as e:
        logger.error("Fail to search images due to error: {}".format(e))
        resp_info["code"] = ReturnCode.SEARCH_FACE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.SEARCH_FACE_ERROR]

        resp_info["data"]["status"] = str(e)

    return resp_info


def query_face(rqst_data, request_files):
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success",
            "image_list": {}
        },
        "seqNo": get_request_sequence_id("query_face")
    }

    try:
        image_id_list = rqst_data.get('image_id_list', None)

        if image_id_list is not None:
            image_id_list = image_id_list.split(',')
            image_id_list = [x.strip() for x in image_id_list]

            if not vectorDB.check_connection():
                vectorDB.reconnect()

            results, err_message = vectorDB.query("image_id", image_id_list)
        else:
            image_name_list = rqst_data.get('image_name_list', None)
            if image_name_list is None:
                raise Exception("Params[{}] or Params[{}] is missing".format("image_id_list", "image_name_list"))

            image_name_list = image_name_list.split(',')
            image_name_list = [x.strip() for x in image_name_list]

            if not vectorDB.check_connection():
                vectorDB.reconnect()

            results, err_message = vectorDB.query("image_name", image_name_list)

        if len(err_message) > 0:
            raise Exception(err_message)
        else:
            resp_info["data"]["image_list"] = results
    except Exception as e:
        logger.error("Fail to query images due to error: {}".format(e))
        resp_info["code"] = ReturnCode.QUERY_FACE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.QUERY_FACE_ERROR]

        resp_info["data"]["status"] = str(e)

    return resp_info


def delete_face(rqst_data, request_files):
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success"
        },
        "seqNo": get_request_sequence_id("delete_face")
    }

    try:
        image_id_list = rqst_data.get('image_id_list', None)

        if image_id_list is not None:
            image_id_list = image_id_list.split(',')
            image_id_list = [x.strip() for x in image_id_list]

            if not vectorDB.check_connection():
                vectorDB.reconnect()

            results, err_message = vectorDB.delete("image_id", image_id_list)
        else:
            image_name_list = rqst_data.get('image_name_list', None)
            if image_name_list is None:
                raise Exception("Params[{}] or Params[{}] is missing".format("image_id_list", "image_name_list"))

            image_name_list = image_name_list.split(',')
            image_name_list = [x.strip() for x in image_name_list]

            if not vectorDB.check_connection():
                vectorDB.reconnect()

            results, err_message = vectorDB.delete("image_name", image_name_list)

        if len(err_message) > 0:
            raise Exception(err_message)

    except Exception as e:
        logger.error("Fail to delete images due to error: {}".format(e))

        resp_info["code"] = ReturnCode.DELETE_FACE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.DELETE_FACE_ERROR]
        resp_info["data"]["status"] = str(e)

    return resp_info


def anti_spoof_face(rqst_data, request_files):
    """
    反欺诈检测 - Celery异步处理版本
    """
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success",
            "image_list": []
        },
        "seqNo": get_request_sequence_id("anti_spoof_face")
    }

    try:
        image_path_list = _extract_image_data(request_files, True)
        if len(image_path_list) == 0:
            raise Exception("Fail to find image data")

        image_items = []
        for i, image_path in enumerate(image_path_list):
            p = image_path.rfind(os.sep)
            q = image_path.rfind('.')
            image_name = image_path[p + 1: q]
            image_id = image_path[q + 1:]

            image_items.append({"image_id": image_id, "image_name": image_name, "image_path": image_path})

        use_multiple_faces = _parse_use_multiple_faces(rqst_data)

        req_uid = get_request_sequence_id(str(image_items))
        req_msg = {"data": image_items, "uid": req_uid, "use_multiple_faces": use_multiple_faces}
        logger.info("prepare to detect spoof face: {}".format(req_msg))

        if _redis.push_data(req_msg, ServiceMessageKey.ANTI_SPOOF_FACE_MESSAGE_KEY.value) < 0:
            raise Exception(
                "Fail to push data to redis queue: {}".format(ServiceMessageKey.ANTI_SPOOF_FACE_MESSAGE_KEY.value))
        else:
            resp_info = _redis.pop_data(req_uid, True)

    except Exception as e:
        logger.error("Fail to detect spoof face due to error: {}".format(e))

        resp_info["code"] = ReturnCode.ANTI_SPOOF_IMAGE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.ANTI_SPOOF_IMAGE_ERROR]
        resp_info["data"]["status"] = str(e)

    return resp_info


def anti_spoof_face_by_image_id(rqst_data, request_files):
    """
    按图片ID进行反欺诈检测 - Celery异步处理版本
    """
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success",
            "image_list": {}
        },
        "seqNo": get_request_sequence_id("anti_spoof_face_by_image_id")
    }

    try:
        image_items = _parse_image_items_from_image_id(rqst_data)

        use_multiple_faces = _parse_use_multiple_faces(rqst_data)

        req_uid = get_request_sequence_id(str(image_items))
        req_msg = {"data": image_items, "uid": req_uid, "use_multiple_faces": use_multiple_faces}

        logger.info("prepare to detect spoof face: {}".format(req_msg))

        if _redis.push_data(req_msg, ServiceMessageKey.ANTI_SPOOF_FACE_MESSAGE_KEY.value) < 0:
            raise Exception(
                "Fail to push data to redis queue: {}".format(ServiceMessageKey.ANTI_SPOOF_FACE_MESSAGE_KEY.value))
        else:
            resp_info = _redis.pop_data(req_uid, True)

    except Exception as e:
        logger.error("Fail to detect spoof face due to error: {}".format(e))

        resp_info["code"] = ReturnCode.ANTI_SPOOF_IMAGE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.ANTI_SPOOF_IMAGE_ERROR]
        resp_info["data"]["status"] = str(e)

    return resp_info


def _detect_mask_face(image_items, use_multiple_faces):
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

    # logger.info("extracted face: {}".format(valid_image_features))

    if len(valid_image_features) == 0:
        raise Exception("No face detected")

    maskFaceModel.setup(valid_image_features)

    if use_multiple_faces:
        result_items, err_items = maskFaceModel.detect_multi_faces()
    else:
        result_items, err_items = maskFaceModel.detect_single_face()

    return result_items, err_items


def detect_mask_face(rqst_data, request_files):
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success"
        },
        "seqNo": get_request_sequence_id("detect_mask_face")
    }

    try:
        image_path_list = _extract_image_data(request_files, True)
        if len(image_path_list) == 0:
            raise Exception("Fail to find image data")

        image_items = []
        for i, image_path in enumerate(image_path_list):
            p = image_path.rfind(os.sep)
            q = image_path.rfind('.')
            image_name = image_path[p + 1: q]
            image_id = image_path[q + 1:]

            image_items.append({"image_id": image_id, "image_name": image_name, "image_path": image_path})

        use_multiple_faces = _parse_use_multiple_faces(rqst_data)

        result_items, err_items = _detect_mask_face(image_items, use_multiple_faces)

        logger.info("detected mask face: {}".format(result_items))

        if len(err_items) > 0:
            raise Exception(err_items)
        else:
            resp_info["data"]["image_list"] = result_items

    except Exception as e:
        logger.error("Fail to detect mask face due to error: {}".format(e))

        resp_info["code"] = ReturnCode.MASK_FACE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.MASK_FACE_ERROR]
        resp_info["data"]["status"] = str(e)

    return resp_info


def detect_mask_face_by_image_id(rqst_data, request_files):
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success"
        },
        "seqNo": get_request_sequence_id("detect_mask_face_by_image_id")
    }

    try:
        image_items = _parse_image_items_from_image_id(rqst_data)

        use_multiple_faces = _parse_use_multiple_faces(rqst_data)

        result_items, err_items = _detect_mask_face(image_items, use_multiple_faces)

        logger.info("detected mask face: {}".format(result_items))

        if len(err_items) > 0:
            raise Exception(err_items)
        else:
            resp_info["data"]["image_list"] = result_items

    except Exception as e:
        logger.error("Fail to detect mask face due to error: {}".format(e))

        resp_info["code"] = ReturnCode.MASK_FACE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.MASK_FACE_ERROR]
        resp_info["data"]["status"] = str(e)
    return resp_info


def detect_mask_face_by_image_url(rqst_data, request_files):
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success"
        },
        "seqNo": get_request_sequence_id("detect_mask_face_by_image_url")
    }

    try:
        image_items = _parse_image_items_from_image_url(rqst_data)

        use_multiple_faces = _parse_use_multiple_faces(rqst_data)

        result_items, err_items = _detect_mask_face(image_items, use_multiple_faces)

        logger.info("detected mask face: {}".format(result_items))

        if len(err_items) > 0:
            raise Exception(err_items)
        else:
            resp_info["data"]["image_list"] = result_items

    except Exception as e:
        logger.error("Fail to detect mask face due to error: {}".format(e))

        resp_info["code"] = ReturnCode.MASK_FACE_ERROR.value
        resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.MASK_FACE_ERROR]
        resp_info["data"]["status"] = str(e)

    return resp_info


def assess_image_quality(rqst_data, request_files):
    """
    人脸图像质量检测API - 完全防崩溃版本 with 详细日志
    """
    # 立即输出日志表示函数被调用
    logger.info("*** assess_image_quality 函数被调用 ***")
    logger.info(f"*** 参数rqst_data: {rqst_data} ***")
    logger.info(f"*** 参数request_files类型: {type(request_files)} ***")
    
    resp_info = {
        "code": ReturnCode.SUCCESS_CODE.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.SUCCESS_CODE],
        "data": {
            "status": "success",
            "results": []
        },
        "seqNo": get_request_sequence_id("assess_image_quality")
    }

    has_errors = False  # 标记是否有错误
    
    # 添加最外层的安全网 - 防止任何未捕获的异常
    try:
        try:
            logger.info("=== 开始人脸质量检测 ===")
            logger.info(f"请求参数: {rqst_data}")
            logger.info(f"请求文件数量: {len(request_files) if request_files else 0}")
            
            # 详细记录request_files的结构
            if request_files:
                for key, value in request_files.items():
                    logger.info(f"request_files[{key}]: 类型={type(value)}, 长度={len(value) if hasattr(value, '__len__') else 'N/A'}")
                    if key == 'image' and isinstance(value, list):
                        for i, item in enumerate(value):
                            if isinstance(item, dict):
                                item_info = {k: (len(v) if k == 'body' and v else str(v)[:100]) for k, v in item.items()}
                                logger.info(f"  image[{i}]: {item_info}")
            
            # 1. 提取图像数据 - 最外层保护
            try:
                logger.info("开始提取图像数据...")
                image_path_list = _extract_image_data(request_files, True)
                if len(image_path_list) == 0:
                    raise Exception("未找到有效的图像数据")
                logger.info(f"成功提取 {len(image_path_list)} 张图像")
            except Exception as extract_error:
                logger.error(f"图像提取失败: {str(extract_error)}")
                # 判断是否为图像格式错误
                error_msg = str(extract_error).lower()
                if any(keyword in error_msg for keyword in ['not a valid image format', 'image format', 'format error']):
                    resp_info["code"] = ReturnCode.IMAGE_FORMAT_ERROR.value
                    resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.IMAGE_FORMAT_ERROR]
                else:
                    resp_info["code"] = ReturnCode.UPLOAD_IMAGE_ERROR.value
                    resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.UPLOAD_IMAGE_ERROR]
                
                resp_info["data"]["status"] = str(extract_error)
                resp_info["data"]["results"].append({
                    "error": f"图像提取失败: {str(extract_error)}",
                    "overall_quality": "UNQUALIFIED",
                    "overall_score": 0,
                    "timestamp": str(time.time())
                })
                # 这里不能用return，会跳出所有try块
                raise Exception(f"图像提取失败，终止处理: {str(extract_error)}")

            # 2. 处理每张图像 - 独立保护每张图像
            for i, image_path in enumerate(image_path_list):
                logger.info(f"开始处理第 {i+1} 张图像: {image_path}")
                
                # 验证文件存在性
                try:
                    if not os.path.exists(image_path):
                        logger.error(f"文件不存在: {image_path}")
                        resp_info["data"]["results"].append({
                            "image_name": f"missing_{i}",
                            "image_id": get_request_sequence_id(f"missing_{i}"),
                            "overall_quality": "UNQUALIFIED",
                            "overall_score": 0,
                            "face_detected": False,
                            "quality_issues": ["文件不存在"],
                            "timestamp": str(time.time())
                        })
                        continue
                        
                    file_size = os.path.getsize(image_path)
                    logger.info(f"文件存在，大小: {file_size} bytes")
                    
                except Exception as file_check_error:
                    logger.error(f"文件检查失败: {str(file_check_error)}")
                    resp_info["data"]["results"].append({
                        "image_name": f"error_{i}",
                        "image_id": get_request_sequence_id(f"error_{i}"),
                        "overall_quality": "UNQUALIFIED",
                        "overall_score": 0,
                        "face_detected": False,
                        "quality_issues": [f"文件检查失败: {str(file_check_error)}"],
                        "timestamp": str(time.time())
                    })
                    continue
                
                # 为每张图像创建独立的错误处理
                try:
                    # 初始化变量防止未定义错误
                    image_name = f"unknown_{i}"
                    image_id = get_request_sequence_id(f"unknown_{i}")
                    num_faces = 0
                    
                    # 基本信息提取
                    try:
                        p = image_path.rfind(os.sep)
                        q = image_path.rfind('.')
                        image_name = image_path[p + 1: q] if p >= 0 and q > p else os.path.basename(image_path)
                        image_id = image_path[q + 1:] if q >= 0 else get_request_sequence_id(image_name)
                    except Exception as name_error:
                        logger.error(f"文件名解析失败: {str(name_error)}")
                        # 保持默认值

                    # 人脸检测 - 独立保护
                    try:
                        logger.info(f"开始人脸检测: {image_path}")
                        image_items = [{"image_id": image_id, "image_name": image_name, "image_path": image_path}]
                        logger.info(f"设置人脸模型...")
                        faceModel.setup(image_items)
                        logger.info(f"开始提取人脸特征...")
                        valid_image_features, invalid_image_features = faceModel.extract()
                        logger.info(f"人脸检测完成: valid={len(valid_image_features) if valid_image_features else 0}, invalid={len(invalid_image_features) if invalid_image_features else 0}")
                    except Exception as face_detect_error:
                        logger.error(f"人脸检测过程失败: {str(face_detect_error)}")
                        import traceback
                        logger.error(f"人脸检测异常堆栈: {traceback.format_exc()}")
                        resp_info["data"]["results"].append({
                            "image_name": image_name,
                            "image_id": image_id,
                            "overall_quality": "UNQUALIFIED",
                            "overall_score": 0,
                            "face_detected": False,
                            "quality_issues": [f"人脸检测过程失败: {str(face_detect_error)}"],
                            "timestamp": str(time.time())
                        })
                        continue

                    # 检查检测结果
                    if len(invalid_image_features) > 0:
                        error_info = invalid_image_features[0].get("error_info", "未知错误")
                        resp_info["data"]["results"].append({
                            "image_name": image_name,
                            "image_id": image_id,
                            "overall_quality": "UNQUALIFIED",
                            "overall_score": 0,
                            "face_detected": False,
                            "quality_issues": ["人脸检测失败"],
                            "quality_details": {"error_message": error_info},
                            "timestamp": str(time.time())
                        })
                        logger.warning(f"图像 {image_name} 人脸检测失败: {error_info}")
                        continue

                    # 获取人脸信息 - 独立保护
                    try:
                        face_features = valid_image_features[0]
                        max_face_box = face_features.get("max_face_box")
                        num_faces = face_features.get("num_faces", 0)
                        
                        if max_face_box is None or len(max_face_box) < 4:
                            resp_info["data"]["results"].append({
                                "image_name": image_name,
                                "image_id": image_id,
                                "overall_quality": "UNQUALIFIED",
                                "overall_score": 0,
                                "face_detected": True,
                                "quality_issues": ["人脸框信息无效"],
                                "quality_details": {"num_faces": num_faces},
                                "timestamp": str(time.time())
                            })
                            continue
                    except Exception as face_info_error:
                        logger.error(f"人脸信息处理失败: {str(face_info_error)}")
                        resp_info["data"]["results"].append({
                            "image_name": image_name,
                            "image_id": image_id,
                            "overall_quality": "UNQUALIFIED",
                            "overall_score": 0,
                            "face_detected": False,
                            "quality_issues": [f"人脸信息处理失败: {str(face_info_error)}"],
                            "timestamp": str(time.time())
                        })
                        continue

                    # 图像读取和质量分析 - 使用缓存图像避免重复读取
                    try:
                        import cv2
                        
                        # 优先使用InsightFace已读取的缓存图像
                        cached_image = face_features.get("cached_image")
                        if cached_image is not None:
                            image = cached_image
                            logger.info(f"使用缓存图像，避免重复读取")
                        else:
                            logger.info(f"开始读取图像: {image_path}")
                            image = cv2.imread(image_path)
                            if image is None:
                                raise Exception(f"cv2无法读取图像: {image_path}")
                        
                        height, width = image.shape[:2]
                        logger.info(f"图像读取成功，尺寸: {width}x{height}")
                        
                        # 使用完整的质量评分系统
                        try:
                            logger.info(f"尝试使用完整质量评分系统...")
                            quality_result = _faceQualityScorer.comprehensive_quality_assessment(
                                image, max_face_box, image_name, image_id, num_faces
                            )
                            
                            # 确保结果包含所有必要字段
                            if "overall_quality" not in quality_result:
                                raise Exception("质量评分系统返回结果不完整")
                                
                            logger.info(f"完整评分系统成功: {quality_result['overall_quality']} ({quality_result['overall_score']}分)")
                            
                        except Exception as scoring_error:
                            logger.warning(f"完整评分系统失败，使用改进的简化评分: {str(scoring_error)}")
                            import traceback
                            logger.warning(f"评分系统异常堆栈: {traceback.format_exc()}")
                            
                            # 改进的简化评分 - 包含人脸框扩大算法
                            try:
                                original_face_width = max_face_box[2] - max_face_box[0]
                                original_face_height = max_face_box[3] - max_face_box[1]
                                
                                # 防止零值或负值
                                if original_face_width <= 0 or original_face_height <= 0:
                                    raise ValueError(f"无效的人脸框尺寸: {original_face_width}x{original_face_height}")
                                    
                                logger.info(f"原始人脸框: {original_face_width}x{original_face_height}")
                                
                                # 计算扩大后的人脸框 (扩大1.4倍) - 解决InsightFace检测框太小问题
                                expansion_factor = 1.4
                                center_x = (max_face_box[0] + max_face_box[2]) / 2
                                center_y = (max_face_box[1] + max_face_box[3]) / 2
                                
                                expanded_width = original_face_width * expansion_factor
                                expanded_height = original_face_height * expansion_factor
                                
                                # 计算新的边界，确保不超出图像范围
                                new_x1 = max(0, center_x - expanded_width / 2)
                                new_y1 = max(0, center_y - expanded_height / 2)
                                new_x2 = min(width, center_x + expanded_width / 2)
                                new_y2 = min(height, center_y + expanded_height / 2)
                                
                                # 使用扩大后的人脸框计算面积
                                face_width = new_x2 - new_x1
                                face_height = new_y2 - new_y1
                                face_area = face_width * face_height
                                image_area = width * height
                                
                                # 防止除零错误
                                if image_area <= 0:
                                    raise ValueError(f"无效的图像面积: {image_area}")
                                    
                                face_ratio = face_area / image_area
                                
                                logger.info(f"扩大后人脸框: {face_width:.1f}x{face_height:.1f}, 占比: {face_ratio*100:.2f}%")
                                
                                # 评分逻辑 - 基于扩大后的人脸占比
                                if face_ratio < 0.05:
                                    overall_score = 20
                                    quality_grade = "UNQUALIFIED"
                                elif face_ratio < 0.08:
                                    overall_score = 45
                                    quality_grade = "POOR"
                                elif face_ratio < 0.15:
                                    overall_score = 65
                                    quality_grade = "FAIR"
                                elif face_ratio < 0.25:
                                    overall_score = 85
                                    quality_grade = "GOOD"
                                else:
                                    overall_score = 95
                                    quality_grade = "EXCELLENT"
                                
                                # 计算面部中心偏移
                                face_center_x = (max_face_box[0] + max_face_box[2]) / 2
                                face_center_y = (max_face_box[1] + max_face_box[3]) / 2
                                image_center_x = width / 2
                                image_center_y = height / 2
                                center_offset = ((face_center_x - image_center_x) ** 2 + (face_center_y - image_center_y) ** 2) ** 0.5
                                normalized_offset = center_offset / (width * 0.5)  # 归一化到图像宽度的一半
                                
                                # 计算亮度
                                face_region = image[int(max_face_box[1]):int(max_face_box[3]), int(max_face_box[0]):int(max_face_box[2])]
                                brightness = float(np.mean(face_region))
                                
                                # 详细评分
                                size_score = min(100, (face_ratio / 0.15) * 100) if face_ratio > 0 else 0
                                position_score = max(0, 100 - (normalized_offset * 200))
                                brightness_score = 100 if 80 <= brightness <= 180 else max(0, 100 - abs(brightness - 130))
                                sharpness_score = 100  # 简化处理
                                
                                quality_result = {
                                    "image_name": image_name,
                                    "image_id": image_id,
                                    "overall_quality": quality_grade,
                                    "overall_score": float(overall_score),  # 确保是 Python float
                                    "is_qualified": bool(overall_score >= 60),  # 确保是 Python bool
                                    "face_detected": True,
                                    "quality_issues": ["人脸过小"] if face_ratio < 0.08 else [],
                                    "quality_details": {
                                        "face_size_ratio": round(face_ratio, 4),
                                        "face_size_percentage": round(face_ratio * 100, 2),
                                        "face_width": int(face_width),
                                        "face_height": int(face_height),
                                        "image_width": int(width),
                                        "image_height": int(height),
                                        "num_faces": int(num_faces),
                                        "original_face_box": [int(x) for x in max_face_box],
                                        "expanded_face_box": [int(new_x1), int(new_y1), int(new_x2), int(new_y2)],
                                        "expansion_factor": float(expansion_factor),
                                        "original_face_ratio": round((original_face_width * original_face_height) / image_area, 4),
                                        "face_center_offset": round(normalized_offset, 3),
                                        "brightness": round(brightness, 1),
                                        "detailed_scores": {
                                            "size_score": int(size_score),
                                            "position_score": int(position_score),
                                            "brightness_score": int(brightness_score),
                                            "sharpness_score": int(sharpness_score)
                                        }
                                    },
                                    "timestamp": str(time.time())
                                }
                                
                            except Exception as calc_error:
                                logger.error(f"简化评分计算失败: {str(calc_error)}")
                                # 计算失败的兜底结果
                                quality_result = {
                                    "image_name": image_name,
                                    "image_id": image_id,
                                    "overall_quality": "UNQUALIFIED",
                                    "overall_score": 0.0,
                                    "is_qualified": False,
                                    "face_detected": True,
                                    "quality_issues": [f"计算失败: {str(calc_error)}"],
                                    "quality_details": {"num_faces": int(num_faces)},
                                    "timestamp": str(time.time())
                                }
                        
                        resp_info["data"]["results"].append(quality_result)
                        # 从结果中获取质量等级用于日志记录
                        result_quality = quality_result.get("overall_quality", "UNKNOWN")
                        result_score = quality_result.get("overall_score", 0)
                        logger.info(f"图像 {image_name} 处理成功: {result_quality} ({result_score}分)")
                        
                    except Exception as analysis_error:
                        logger.error(f"质量分析失败: {str(analysis_error)}")
                        import traceback
                        logger.error(traceback.format_exc())
                        
                        # 分析失败的兜底结果
                        resp_info["data"]["results"].append({
                            "image_name": image_name,
                            "image_id": image_id,
                            "overall_quality": "UNQUALIFIED",
                            "overall_score": 0,
                            "face_detected": True,
                            "quality_issues": [f"分析失败: {str(analysis_error)}"],
                            "quality_details": {"num_faces": locals().get('num_faces', 0)},
                            "timestamp": str(time.time())
                        })

                    # 清理内存，包括缓存的图像
                    try:
                        # 清理缓存图像避免内存泄漏
                        if 'cached_image' in face_features:
                            del face_features['cached_image']
                        del valid_image_features
                    except:
                        pass

                except Exception as img_error:
                    logger.error(f"处理图像 {image_path} 完全失败: {str(img_error)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    # 完全失败的兜底结果
                    resp_info["data"]["results"].append({
                        "image_name": os.path.basename(image_path) if image_path else "unknown",
                        "image_id": get_request_sequence_id("error"),
                        "overall_quality": "UNQUALIFIED",
                        "overall_score": 0,
                        "face_detected": False,
                        "quality_issues": [f"完全处理失败: {str(img_error)}"],
                        "error_type": type(img_error).__name__,
                        "timestamp": str(time.time())
                    })

            logger.info("=== 人脸质量检测完成 ===")

        except Exception as e:
            # 内层异常处理
            logger.error(f"质量检测内层异常: {str(e)}")
            import traceback
            logger.error(f"内层异常堆栈: {traceback.format_exc()}")
            
            resp_info["data"]["status"] = f"处理过程中发生异常: {str(e)}"
            
            # 确保至少有一个结果
            if not resp_info["data"]["results"]:
                resp_info["data"]["results"].append({
                    "overall_quality": "UNQUALIFIED",
                    "overall_score": 0,
                    "face_detected": False,
                    "quality_issues": [f"内层异常: {str(e)}"],
                    "error_type": type(e).__name__,
                    "timestamp": str(time.time())
                })

    except BaseException as be:
        # 捕获所有可能的异常，包括系统级异常
        logger.error(f"捕获到BaseException: {str(be)}")
        import traceback
        logger.error(f"BaseException堆栈: {traceback.format_exc()}")
        
        # 强制创建安全的响应
        resp_info = {
            "code": ReturnCode.SUCCESS_CODE.value,
            "message": "系统异常但已恢复",
            "data": {
                "status": f"系统级异常: {str(be)}",
                "results": [{
                    "overall_quality": "UNQUALIFIED",
                    "overall_score": 0,
                    "face_detected": False,
                    "quality_issues": [f"系统级异常: {str(be)}"],
                    "error_type": type(be).__name__,
                    "timestamp": str(time.time())
                }]
            },
            "seqNo": get_request_sequence_id("base_exception")
        }

    # 统一错误代码处理：检查是否有质量检测失败的情况
    if resp_info and "data" in resp_info and "results" in resp_info["data"]:
        for result in resp_info["data"]["results"]:
            if result.get("overall_quality") == "UNQUALIFIED" or not result.get("face_detected", False):
                # 只要有任何质量检测失败的情况，就返回统一的错误码
                resp_info["code"] = ReturnCode.IMAGE_QUALITY_ERROR.value
                resp_info["message"] = serviceConf.RETURN_CODE_MAP[ReturnCode.IMAGE_QUALITY_ERROR]
                resp_info["data"]["status"] = "error"  # 同时修改data.status为error
                break

    return resp_info


def not_supported_api(api_name):
    return {
        "code": ReturnCode.NOT_SUPPORTED_ERROR.value,
        "message": serviceConf.RETURN_CODE_MAP[ReturnCode.NOT_SUPPORTED_ERROR],
        "data": {
            "status": "error",
            "message": "API: {} is not supported".format(api_name)
        },
        "seqNo": get_request_sequence_id("not_supported_api")
    }


service_handler = {
    "compare_faces": compare_faces,
    "compare_faces_by_image_id": compare_faces_by_image_id,
    "single_upload_face": single_upload_face,
    "batch_upload_face": batch_upload_face,
    "search_face": search_face,
    "search_face_by_image_id": search_face_by_image_id,
    "query_face": query_face,
    "delete_face": delete_face,
    "anti_spoof_face": anti_spoof_face,
    "anti_spoof_face_by_image_id": anti_spoof_face_by_image_id,
    "detect_mask_face": detect_mask_face,
    "detect_mask_face_by_image_id": detect_mask_face_by_image_id,
    "detect_mask_face_by_image_url": detect_mask_face_by_image_url,
    "assess_image_quality": assess_image_quality
}


@celery_app.task
def handle(service_id, rqst_data, request_files):
    start = time.time()
    logger.info("=== start celery task ===")
    logger.info(rqst_data)

    global _redis, max_api_calls
    if not _redis.check_connection():
        _redis = RedisDBWrapper()

    call_cnt = 0
    if deploy_for_evaluation:
        max_api_calls = _redis.get_handler().get(max_api_calls_name)
        if max_api_calls is None:
            max_api_calls = encrypt_xor(1, magic_num)
        else:
            max_api_calls = int(max_api_calls)

        call_cnt = _redis.get_handler().get(invoke_cnt_name)

        if call_cnt is None:
            call_cnt = encrypt_xor(1, magic_num)
        else:
            call_cnt = int(call_cnt)

        if decrypt_xor(call_cnt, magic_num) > decrypt_xor(max_api_calls, magic_num):
            return  {
                "code": ReturnCode.CALL_API_EXPIRED_ERROR.value,
                "message": serviceConf.RETURN_CODE_MAP[ReturnCode.CALL_API_EXPIRED_ERROR],
                "data": {
                    "status": "error",
                    "message": "[{}] failed to call due to licence expiration".format(service_id)
                },
                "seqNo": get_request_sequence_id("api_call_expiration")
            }                            
        else:
            call_cnt = decrypt_xor(call_cnt, magic_num)
            call_cnt += 1

            _redis.get_handler().set(invoke_cnt_name, encrypt_xor(call_cnt, magic_num))

    if service_id in service_handler:
        resp_info = service_handler[service_id](rqst_data, request_files)
    else:
        resp_info = not_supported_api(service_id)

    end = time.time()
    logger.info("rqst_data={rqst_data}\tresp_info={resp_info}\ttime_cost={time_cost}".format(
        rqst_data=json.dumps(rqst_data),
        resp_info=json.dumps(resp_info, ensure_ascii=False),
        time_cost=end - start)
    )

    return resp_info
