import os
import sys
import cv2
import torch
import numpy as np
from libs import log
from conf.model_config import MaskConf

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from models.model import Model

logger = log.get_logger("face-model")

id2class = {0: 'Mask', 1: 'NoMask'}


class MaskModel(Model):

    def __init__(self):
        super(MaskModel, self).__init__()

        # for inference , the batch size is 1, the model output shape is [1, N, 4],
        # so we expand dim for anchors to [1, anchor_num, 4]
        anchors = MaskModel.generate_anchors(MaskConf.feature_map_sizes, MaskConf.anchor_sizes, MaskConf.anchor_ratios)
        self.__anchors = np.expand_dims(anchors, axis=0)

        self.__model = torch.load(MaskConf.model_path)
        if torch.cuda.is_available():
            dev = 'cuda:0'
        else:
            dev = 'cpu'
        self.__device = torch.device(dev)
        self.__model.to(self.__device)

    def setup(self, image_items):
        super(MaskModel, self).setup(image_items)

    def detect_single_face(self):
        result_items = []
        error_items = []
        this_item = None

        try:
            for image_item in self._image_items:
                this_item = image_item

                img = cv2.imread(image_item["image_path"])
                x1, y1, x2, y2 = image_item["max_face_box"]

                img = img[int(y1):int(y2), int(x1):int(x2)]
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                height, width, _ = img.shape
                image_resized = cv2.resize(img, (360, 360))
                image_np = image_resized / 255.0  # 归一化到0~1
                image_exp = np.expand_dims(image_np, axis=0)

                image_transposed = image_exp.transpose((0, 3, 1, 2))

                y_bboxes_output, y_cls_output = self.inference(image_transposed)
                # remove the batch dimension, for batch is always 1 for inference.
                y_bboxes = MaskModel.decode_bbox(self.__anchors, y_bboxes_output)[0]
                y_cls = y_cls_output[0]
                # To speed up, do single class NMS, not multiple classes NMS.
                bbox_max_scores = np.max(y_cls, axis=1)
                bbox_max_score_classes = np.argmax(y_cls, axis=1)

                # keep_idx is the alive bounding box after nms.
                keep_idxs = MaskModel.single_class_non_max_suppression(y_bboxes, bbox_max_scores,
                                                                       conf_thresh=MaskConf.conf_thresh,
                                                                       iou_thresh=MaskConf.iou_thresh)

                idx = keep_idxs[0]
                prob = float(bbox_max_scores[idx])
                class_id = bbox_max_score_classes[idx]
                bbox = y_bboxes[idx]
                # clip the coordinate, avoid the value exceed the image boundary.
                xmin = max(0, int(bbox[0] * width))
                ymin = max(0, int(bbox[1] * height))
                xmax = min(int(bbox[2] * width), width)
                ymax = min(int(bbox[3] * height), height)

                result_items.append({"image_id": image_item["image_id"], "image_name": image_item["image_name"],
                                     "image_path": image_item["image_path"], "num_faces": image_item["num_faces"],
                                     "face_id": image_item["max_face_idx"], "face_box": [int(x1), int(y1), int(x2), int(y2)],
                                     "face_mask_check": id2class[class_id], "face_mask_box": [int(xmin), int(ymin), int(xmax), int(ymax)]})

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
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                height, width, _ = img.shape
                image_resized = cv2.resize(img, (360, 360))
                image_np = image_resized / 255.0  # 归一化到0~1
                image_exp = np.expand_dims(image_np, axis=0)

                image_transposed = image_exp.transpose((0, 3, 1, 2))

                y_bboxes_output, y_cls_output = self.inference(image_transposed)
                # remove the batch dimension, for batch is always 1 for inference.
                y_bboxes = MaskModel.decode_bbox(self.__anchors, y_bboxes_output)[0]
                y_cls = y_cls_output[0]
                # To speed up, do single class NMS, not multiple classes NMS.
                bbox_max_scores = np.max(y_cls, axis=1)
                bbox_max_score_classes = np.argmax(y_cls, axis=1)

                # keep_idx is the alive bounding box after nms.
                keep_idxs = MaskModel.single_class_non_max_suppression(y_bboxes, bbox_max_scores,
                                                                       conf_thresh=MaskConf.conf_thresh,
                                                                       iou_thresh=MaskConf.iou_thresh)

                for face_idx, mask_idx in enumerate(keep_idxs):
                    prob = float(bbox_max_scores[mask_idx])
                    class_id = bbox_max_score_classes[mask_idx]
                    bbox = y_bboxes[mask_idx]
                    # clip the coordinate, avoid the value exceed the image boundary.
                    xmin, ymin, xmax, ymax = [0] * 4

                    if class_id == 0:
                        xmin = max(0, int(bbox[0] * width))
                        ymin = max(0, int(bbox[1] * height))
                        xmax = min(int(bbox[2] * width), width)
                        ymax = min(int(bbox[3] * height), height)

                    x1, y1, x2, y2 = [0] * 4

                    if face_idx < len(image_item["face_boxes"]):
                        face_box = image_item["face_boxes"][face_idx]
                        x1, y1, x2, y2 = face_box

                    result_items.append({"image_id": image_item["image_id"], "image_name": image_item["image_name"],
                                         "image_path": image_item["image_path"], "num_faces": image_item["num_faces"],
                                         "face_id": face_idx, "face_box": [int(x1), int(y1), int(x2), int(y2)],
                                         "face_mask_check": id2class[class_id],
                                         "face_mask_box": [int(xmin), int(ymin), int(xmax), int(ymax)]})

            return result_items, []
        except Exception as e:
            error_items.append({"image_id": this_item["image_id"], "image_name": this_item["image_name"],
                                "image_path": this_item["image_path"], "error_info": repr(e)})

            return [], error_items

    def inference(self, img):

        input_tensor = torch.tensor(img).float().to(self.__device)
        y_bboxes, y_scores, = self.__model.forward(input_tensor)
        return y_bboxes.detach().cpu().numpy(), y_scores.detach().cpu().numpy()

    @staticmethod
    def generate_anchors(feature_map_sizes, anchor_sizes, anchor_ratios, offset=0.5):
        '''
        generate anchors.
        :param feature_map_sizes: list of list, for example: [[40,40], [20,20]]
        :param anchor_sizes: list of list, for example: [[0.05, 0.075], [0.1, 0.15]]
        :param anchor_ratios: list of list, for example: [[1, 0.5], [1, 0.5]]
        :param offset: default to 0.5
        :return:
        '''
        anchor_bboxes = []
        for idx, feature_size in enumerate(feature_map_sizes):
            cx = (np.linspace(0, feature_size[0] - 1, feature_size[0]) + 0.5) / feature_size[0]
            cy = (np.linspace(0, feature_size[1] - 1, feature_size[1]) + 0.5) / feature_size[1]
            cx_grid, cy_grid = np.meshgrid(cx, cy)
            cx_grid_expend = np.expand_dims(cx_grid, axis=-1)
            cy_grid_expend = np.expand_dims(cy_grid, axis=-1)
            center = np.concatenate((cx_grid_expend, cy_grid_expend), axis=-1)

            num_anchors = len(anchor_sizes[idx]) + len(anchor_ratios[idx]) - 1
            center_tiled = np.tile(center, (1, 1, 2 * num_anchors))
            anchor_width_heights = []

            # different scales with the first aspect ratio
            for scale in anchor_sizes[idx]:
                ratio = anchor_ratios[idx][0]  # select the first ratio
                width = scale * np.sqrt(ratio)
                height = scale / np.sqrt(ratio)
                anchor_width_heights.extend([-width / 2.0, -height / 2.0, width / 2.0, height / 2.0])

            # the first scale, with different aspect ratios (except the first one)
            for ratio in anchor_ratios[idx][1:]:
                s1 = anchor_sizes[idx][0]  # select the first scale
                width = s1 * np.sqrt(ratio)
                height = s1 / np.sqrt(ratio)
                anchor_width_heights.extend([-width / 2.0, -height / 2.0, width / 2.0, height / 2.0])

            bbox_coords = center_tiled + np.array(anchor_width_heights)
            bbox_coords_reshape = bbox_coords.reshape((-1, 4))
            anchor_bboxes.append(bbox_coords_reshape)
        anchor_bboxes = np.concatenate(anchor_bboxes, axis=0)
        return anchor_bboxes

    @staticmethod
    def decode_bbox(anchors, raw_outputs, variances=[0.1, 0.1, 0.2, 0.2]):
        '''
        Decode the actual bbox according to the anchors.
        the anchor value order is:[xmin,ymin, xmax, ymax]
        :param anchors: numpy array with shape [batch, num_anchors, 4]
        :param raw_outputs: numpy array with the same shape with anchors
        :param variances: list of float, default=[0.1, 0.1, 0.2, 0.2]
        :return:
        '''
        anchor_centers_x = (anchors[:, :, 0:1] + anchors[:, :, 2:3]) / 2
        anchor_centers_y = (anchors[:, :, 1:2] + anchors[:, :, 3:]) / 2
        anchors_w = anchors[:, :, 2:3] - anchors[:, :, 0:1]
        anchors_h = anchors[:, :, 3:] - anchors[:, :, 1:2]
        raw_outputs_rescale = raw_outputs * np.array(variances)
        predict_center_x = raw_outputs_rescale[:, :, 0:1] * anchors_w + anchor_centers_x
        predict_center_y = raw_outputs_rescale[:, :, 1:2] * anchors_h + anchor_centers_y
        predict_w = np.exp(raw_outputs_rescale[:, :, 2:3]) * anchors_w
        predict_h = np.exp(raw_outputs_rescale[:, :, 3:]) * anchors_h
        predict_xmin = predict_center_x - predict_w / 2
        predict_ymin = predict_center_y - predict_h / 2
        predict_xmax = predict_center_x + predict_w / 2
        predict_ymax = predict_center_y + predict_h / 2
        predict_bbox = np.concatenate([predict_xmin, predict_ymin, predict_xmax, predict_ymax], axis=-1)
        return predict_bbox

    @staticmethod
    def single_class_non_max_suppression(bboxes, confidences, conf_thresh=0.2, iou_thresh=0.5, keep_top_k=-1):
        '''
        do nms on single class.
        Hint: for the specific class, given the bbox and its confidence,
        1) sort the bbox according to the confidence from top to down, we call this a set
        2) select the bbox with the highest confidence, remove it from set, and do IOU calculate with the rest bbox
        3) remove the bbox whose IOU is higher than the iou_thresh from the set,
        4) loop step 2 and 3, util the set is empty.
        :param bboxes: numpy array of 2D, [num_bboxes, 4]
        :param confidences: numpy array of 1D. [num_bboxes]
        :param conf_thresh:
        :param iou_thresh:
        :param keep_top_k:
        :return:
        '''
        if len(bboxes) == 0: return []

        conf_keep_idx = np.where(confidences > conf_thresh)[0]

        bboxes = bboxes[conf_keep_idx]
        confidences = confidences[conf_keep_idx]

        pick = []
        xmin = bboxes[:, 0]
        ymin = bboxes[:, 1]
        xmax = bboxes[:, 2]
        ymax = bboxes[:, 3]

        area = (xmax - xmin + 1e-3) * (ymax - ymin + 1e-3)
        idxs = np.argsort(confidences)

        while len(idxs) > 0:
            last = len(idxs) - 1
            i = idxs[last]
            pick.append(i)

            # keep top k
            if keep_top_k != -1:
                if len(pick) >= keep_top_k:
                    break

            overlap_xmin = np.maximum(xmin[i], xmin[idxs[:last]])
            overlap_ymin = np.maximum(ymin[i], ymin[idxs[:last]])
            overlap_xmax = np.minimum(xmax[i], xmax[idxs[:last]])
            overlap_ymax = np.minimum(ymax[i], ymax[idxs[:last]])
            overlap_w = np.maximum(0, overlap_xmax - overlap_xmin)
            overlap_h = np.maximum(0, overlap_ymax - overlap_ymin)
            overlap_area = overlap_w * overlap_h
            overlap_ratio = overlap_area / (area[idxs[:last]] + area[i] - overlap_area)

            need_to_be_deleted_idx = np.concatenate(([last], np.where(overlap_ratio > iou_thresh)[0]))
            idxs = np.delete(idxs, need_to_be_deleted_idx)

        # if the number of final bboxes is less than keep_top_k, we need to pad it.
        # TODO
        return conf_keep_idx[pick]



