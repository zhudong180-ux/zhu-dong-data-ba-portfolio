import cv2
import dlib
import numpy as np
from libs import log
from conf.model_config import CV2DNNConf
from conf.config import serviceConf

from models.model import Model

logger = log.get_logger("cv2dnn-model")


class CV2DNNModel(Model):

    def __init__(self):
        super(CV2DNNModel, self).__init__()

        self.__net = cv2.dnn.readNetFromTensorflow(CV2DNNConf.detection_proto_path, CV2DNNConf.detection_model_path)

        self.__sp = dlib.shape_predictor(CV2DNNConf.shape_model_path)
        self.__recognizer = dlib.face_recognition_model_v1(CV2DNNConf.recognition_model_path)

        if serviceConf.USE_GPU:
            self.__net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            self.__net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)

    def setup(self, image_items):
        super(CV2DNNModel, self).setup(image_items)

    def extract(self):

        invalid_image_list = []
        valid_image_list = []

        image_id = None
        image_name = None
        image_path = None

        for image_item in self._image_items:
            max_face_idx = 0
            face_descriptors = []
            max_face_box = None

            try:
                image_id = image_item["image_id"]
                image_name = image_item["image_name"]
                image_path = image_item["image_path"]

                img = cv2.imread(image_path)

                if img is None:
                    raise Exception("Fail to read {}, maybe it does not exist".format(image_path))

                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                (h, w) = img.shape[:2]
                blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))

                self.__net.setInput(blob)
                detections = self.__net.forward()

                max_face_area = 0

                for i in range(0, detections.shape[2]):
                    confidence = detections[0, 0, i, 2]

                    if confidence > CV2DNNConf.detection_confidence:
                        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                        (startX, startY, endX, endY) = box.astype("int")

                        face_area = abs((endX - startX) * (endY - startY))
                        if face_area > max_face_area:
                            max_face_area = face_area
                            max_face_idx = len(face_descriptors)

                            max_face_box = box.astype("int")

                        rect = dlib.rectangle(startX, startY, endX, endY)

                        shape = self.__sp(img, rect)
                        face_descriptor = np.array(self.__recognizer.compute_face_descriptor(img, shape))
                        face_descriptors.append(face_descriptor)

            except Exception as e:
                logger.error("The image of {} fails to extract face due to {}".format(image_id, e))

                invalid_image_list.append({"image_id": image_id, "image_name": image_name,
                                           "image_path": image_path, "error_info": repr(e)})
                continue

            if len(face_descriptors) > 0:
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
            face_descriptors = []
            face_boxes = []

            try:
                image_id = image_item["image_id"]
                image_name = image_item["image_name"]
                image_path = image_item["image_path"]

                img = cv2.imread(image_path)

                if img is None:
                    raise Exception("Fail to read {}, maybe it does not exist".format(image_path))

                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                (h, w) = img.shape[:2]
                blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))

                self.__net.setInput(blob)
                detections = self.__net.forward()

                for i in range(0, detections.shape[2]):
                    confidence = detections[0, 0, i, 2]

                    if confidence > CV2DNNConf.detection_confidence:
                        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                        (startX, startY, endX, endY) = box.astype("int")

                        face_boxes.append(box.astype("int"))

                        rect = dlib.rectangle(startX, startY, endX, endY)

                        shape = self.__sp(img, rect)
                        face_descriptor = np.array(self.__recognizer.compute_face_descriptor(img, shape))
                        face_descriptors.append(face_descriptor)

            except Exception as e:
                logger.error("The image of {} fails to extract face due to {}".format(image_id, e))

                invalid_image_list.append({"image_id": image_id, "image_name": image_name,
                                           "image_path": image_path, "error_info": repr(e)})
                continue

            if len(face_descriptors) > 0:
                valid_image_list.append({"image_id": image_id, "image_name": image_name, "image_path": image_path,
                                         "num_faces": len(face_descriptors), "face_vectors": face_descriptors,
                                         "face_boxes": face_boxes})
            else:
                logger.error("The image of {} has no face".format(image_path))

                invalid_image_list.append({"image_id": image_id, "image_name": image_name, "image_path": image_path,
                                           "error_info": "no face detected"})

        return valid_image_list, invalid_image_list
