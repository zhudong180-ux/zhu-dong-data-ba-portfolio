import cv2
import dlib
import numpy as np
from libs import log
from conf.model_config import DlibConf
from conf.config import serviceConf

# sys.path.append('./conf')
from models.model import Model

logger = log.get_logger("dlib-model")


class DLibModel(Model):

    def __init__(self):
        super(DLibModel, self).__init__()

        if serviceConf.USE_GPU and dlib.DLIB_USE_CUDA:
            self.__detector = dlib.cnn_face_detection_model_v1(DlibConf.detect_model_path)
        else:
            self.__detector = dlib.get_frontal_face_detector()

        self.__sp = dlib.shape_predictor(DlibConf.shape_model_path)

        self.__recognizer = dlib.face_recognition_model_v1(DlibConf.recognition_model_path)

    def setup(self, image_items):
        super(DLibModel, self).setup(image_items)

    def extract(self):

        invalid_image_list = []
        valid_image_list = []

        image_id = None
        image_name = None
        image_path = None

        for image_item in self._image_items:
            try:
                image_id = image_item["image_id"]
                image_name = image_item["image_name"]
                image_path = image_item["image_path"]

                img = cv2.imread(image_path)

                if img is None:
                    raise Exception("Fail to read {}, maybe it does not exist".format(image_path))

                detections = self.__detector(img, 1)

                if serviceConf.USE_GPU and dlib.DLIB_USE_CUDA:
                    face_descriptors = []
                    for detection in detections:
                        # 提取人脸区域
                        face = dlib.rectangle(left=detection.rect.left(), top=detection.rect.top(),
                                              right=detection.rect.right(), bottom=detection.rect.bottom())
                        shape = self.__sp(img, face)
                        face_descriptors.append(np.array(self.__recognizer.compute_face_descriptor(img, shape)))
                else:
                    shapes = [self.__sp(img, d) for d in detections]
                    face_descriptors = [np.array(self.__recognizer.compute_face_descriptor(img, shape)) for shape in
                                        shapes]

            except Exception as e:
                logger.error("The image of {} fails to extract face due to {}".format(image_id, e))

                invalid_image_list.append({"image_id": image_id, "image_name": image_name,
                                           "image_path": image_path, "error_info": repr(e)})
                continue

            if len(face_descriptors) > 0:
                max_face_idx, max_face_box = DLibModel.__extract_max_face(detections)

                valid_image_list.append({"image_id": image_id, "image_name": image_name, "image_path": image_path,
                                         "num_faces": len(face_descriptors), "face_vectors": face_descriptors,
                                         "max_face_idx": max_face_idx, "max_face_box": max_face_box})
            else:
                logger.error("The image of {} has no face".format(image_path))

                invalid_image_list.append({"image_id": image_id, "image_name": image_name, "image_path": image_path,
                                           "error_info": "no face detected"})

        return valid_image_list, invalid_image_list

    def extract_multiple_faces(self):
        invalid_image_list = []
        valid_image_list = []

        image_id = None
        image_name = None
        image_path = None

        for image_item in self._image_items:
            try:
                image_id = image_item["image_id"]
                image_name = image_item["image_name"]
                image_path = image_item["image_path"]

                img = cv2.imread(image_path)

                if img is None:
                    raise Exception("Fail to read {}, maybe it does not exist".format(image_path))

                detections = self.__detector(img, 1)

                if serviceConf.USE_GPU and dlib.DLIB_USE_CUDA:
                    face_descriptors = []
                    for detection in detections:
                        # 提取人脸区域
                        face = dlib.rectangle(left=detection.rect.left(), top=detection.rect.top(),
                                              right=detection.rect.right(), bottom=detection.rect.bottom())
                        shape = self.__sp(img, face)
                        face_descriptors.append(np.array(self.__recognizer.compute_face_descriptor(img, shape)))
                else:
                    shapes = [self.__sp(img, d) for d in detections]
                    face_descriptors = [np.array(self.__recognizer.compute_face_descriptor(img, shape)) for shape in
                                        shapes]

            except Exception as e:
                logger.error("The image of {} fails to extract face due to {}".format(image_id, e))

                invalid_image_list.append({"image_id": image_id, "image_name": image_name,
                                           "image_path": image_path, "error_info": repr(e)})
                continue

            if len(face_descriptors) > 0:
                valid_image_list.append({"image_id": image_id, "image_name": image_name, "image_path": image_path,
                                         "num_faces": len(face_descriptors), "face_vectors": face_descriptors,
                                         "face_boxes": DLibModel.__extract_face_coordinates(detections)})
            else:
                logger.error("The image of {} has no face".format(image_path))

                invalid_image_list.append({"image_id": image_id, "image_name": image_name, "image_path": image_path,
                                           "error_info": "no face detected"})

        return valid_image_list, invalid_image_list

    @staticmethod
    def __extract_max_face(detections):
        max_face_area = 0
        max_face_idx = 0
        max_face_box = None

        for index, face in enumerate(detections):
            x1, y1, x2, y2 = face.left(), face.top(), face.right(), face.bottom()
            face_area = abs((x2 - x1) * (y2 - y1))
            if face_area > max_face_area:
                max_face_area = face_area
                max_face_idx = index
                max_face_box = [x1, y1, x2, y2]

        return max_face_idx, max_face_box

    @staticmethod
    def __extract_face_coordinates(detections):

        face_boxes = [[x.left(), x.top(), x.right(), x.bottom()] for x in detections]

        return face_boxes
