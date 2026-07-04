import cv2
import datetime
import torch
from libs import log
from models.deepixbis_model import DeePixBisModel
from conf.config import serviceConf

# sys.path.append('./conf')
from models.model import Model

logger = log.get_logger("face-model")


class AntiSpoofModel(Model):

    def __init__(self):
        super(AntiSpoofModel, self).__init__()
        self.__model = DeePixBisModel()

    def setup(self, image_items):
        super(AntiSpoofModel, self).setup(image_items)

    def detect_single_face(self):
        result_items = []
        error_items = []
        this_item = None

        try:
            for image_item in self._image_items:
                this_item = image_item

                img = cv2.imread(image_item["image_path"])
                x1, y1, x2, y2 = image_item["max_face_box"]

                faceRegion = img[int(y1):int(y2), int(x1):int(x2)]
                faceRegion = cv2.cvtColor(faceRegion, cv2.COLOR_BGR2RGB)

                faceRegion = self.__model.preprocess(faceRegion)
                faceRegion = faceRegion.unsqueeze(0)

                mask, binary = self.__model.forward(faceRegion)
                prob = float(torch.mean(mask).item())

                logger.info("{} detected spoof prob:{}".format(image_item["image_name"], prob))

                result_items.append({"image_id": image_item["image_id"], "image_name": image_item["image_name"],
                                     "image_path": image_item["image_path"], "num_faces": image_item["num_faces"],
                                     "face_id": image_item["max_face_idx"], "face_box": [int(x1), int(y1), int(x2), int(y2)],
                                     "real_face_prob": prob})
            return result_items, []
        except Exception as e:
            error_items.append({"image_id": this_item["image_id"], "image_name": this_item["image_name"],
                                "image_path": this_item["image_path"], "error_info": repr(e)})

            return [], error_items

    def detect_multi_faces(self):
        result_items = []
        error_items = []
        this_item = None

        try:
            for image_item in self._image_items:
                this_item = image_item

                img = cv2.imread(image_item["image_path"])

                for face_id, face_box in enumerate(image_item["face_boxes"]):
                    x1, y1, x2, y2 = face_box
                    faceRegion = img[int(y1):int(y2), int(x1):int(x2)]
                    faceRegion = cv2.cvtColor(faceRegion, cv2.COLOR_BGR2RGB)

                    faceRegion = self.__model.preprocess(faceRegion)
                    faceRegion = faceRegion.unsqueeze(0)

                    mask, binary = self.__model.forward(faceRegion)
                    prob = float(torch.mean(mask).item())

                    logger.info("The face[{}] in the image[{}] detected spoof prob:{}".format(face_id,
                                                                                              image_item["image_name"],
                                                                                              prob))

                    result_items.append({"image_id": image_item["image_id"], "image_name": image_item["image_name"],
                                         "image_path": image_item["image_path"], "num_faces": image_item["num_faces"],
                                         "face_id": face_id, "face_box": [int(x1), int(y1), int(x2), int(y2)],
                                         "real_face_prob": prob})

            return result_items, []
        except Exception as e:
            error_items.append({"image_id": this_item["image_id"], "image_name": this_item["image_name"],
                                "image_path": this_item["image_path"], "error_info": repr(e)})

            return [], error_items
