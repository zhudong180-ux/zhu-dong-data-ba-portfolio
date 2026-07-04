
from libs import log
from conf.config import serviceConf

# sys.path.append('./conf')

logger = log.get_logger("model")


class Model(object):

    def __init__(self):
        self._image_items = {}
        self._framework = serviceConf.USE_FRAME

    def setup(self, image_items):
        self._image_items = image_items.copy()

    def get_model_name(self):
        return self._framework.value

    def extract(self):
        pass

    def extract_multiple_faces(self):
        pass

    def predict(self):
        pass


