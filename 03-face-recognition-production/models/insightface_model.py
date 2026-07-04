import cv2

from conf.model_config import InsightFaceConf
from insightface.app import FaceAnalysis

from libs import log
from conf.config import serviceConf

# sys.path.append('./conf')
from models.model import Model

logger = log.get_logger("face-model")


class InsightFaceModel(Model):

    def __init__(self):
        super(InsightFaceModel, self).__init__()

        self.__app = FaceAnalysis(name=InsightFaceConf.model_category)

        if serviceConf.USE_GPU:
            self.__app.prepare(ctx_id=0, det_size=(InsightFaceConf.resize_img_width, InsightFaceConf.resize_img_height))
        else:
            self.__app.prepare(ctx_id=-1,
                               det_size=(InsightFaceConf.resize_img_width, InsightFaceConf.resize_img_height))

    def setup(self, image_items):
        super(InsightFaceModel, self).setup(image_items)

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

                dets = self.__app.get(img)  # shape:(512,)
            except Exception as e:
                logger.error("The image of {} fails to extract face due to {}".format(image_id, e))

                invalid_image_list.append({"image_id": image_id, "image_name": image_name,
                                           "image_path": image_path, "error_info": repr(e)})
                continue

            # 提取特征向量
            face_descriptors = [d.normed_embedding for d in dets]

            if len(face_descriptors) > 0:
                max_face_idx, max_face_box = InsightFaceModel.__extract_max_face(dets)

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

                dets = self.__app.get(img)  # shape:(512,)
            except Exception as e:
                logger.error("The image of {} fails to extract face due to {}".format(image_id, e))

                invalid_image_list.append({"image_id": image_id,
                                           "image_name": image_name,
                                           "image_path": image_path, "error_info": repr(e)})
                continue

            # 提取特征向量
            face_descriptors = [d.normed_embedding for d in dets]

            if len(face_descriptors) > 0:
                valid_image_list.append({"image_id": image_id, "image_name": image_name, "image_path": image_path,
                                         "num_faces": len(face_descriptors), "face_vectors": face_descriptors,
                                         "face_boxes": InsightFaceModel.__extract_face_coordinates(dets)})
            else:
                logger.error("The image of {} has no face".format(image_path))

                invalid_image_list.append({"image_id": image_id, "image_name": image_name, "image_path": image_path,
                                           "error_info": "no face detected"})

        return valid_image_list, invalid_image_list

    def extract_faces_coordinates(self):
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

                dets = self.__app.get(img)  # shape:(512,)
            except Exception as e:
                logger.error("The image of {} fails to extract face due to {}".format(image_id, e))

                invalid_image_list.append({"image_id": image_id, "image_name": image_name,
                                           "image_path": image_path, "error_info": repr(e)})
                continue

            # 提取特征向量
            face_descriptors = [d.normed_embedding for d in dets]

            if len(face_descriptors) > 0:
                valid_image_list.append({"image_id": image_id, "image_name": image_name, "image_path": image_path,
                                         "num_faces": len(face_descriptors),
                                         "face_boxes": InsightFaceModel.__extract_face_coordinates(dets)})
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
            x1, y1, x2, y2 = face.bbox
            face_area = abs((x2 - x1) * (y2 - y1))

            if face_area > max_face_area:
                max_face_area = face_area
                max_face_idx = index
                max_face_box = face.bbox

        return max_face_idx, max_face_box

    @staticmethod
    def __extract_face_coordinates(detections):

        face_boxes = [x.bbox for x in detections]

        return face_boxes

