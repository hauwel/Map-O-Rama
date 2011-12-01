import sys
import math

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import QtNetwork


class OSMMap(QtGui.QWidget):

    def __init__(self, width=800, height=600, parent=None):
        super(OSMMap, self).__init__(parent)
        self.resize(width, height)

        self.zoom = 15
        self.max_zoom = 18
        self.min_zoom = 0
        self.latitude = 56.3217086791992 
        self.longitude = 44.0330696105957
#        self.latitude = 56.329744
#        self.longitude = 43.959904
        self.visible_rect = QtCore.QRect()
        self.tiles = dict()
        self.x_offset = None
        self.y_offset = None
        
        self.tile_res = 256
        self.no_pixmap = QtGui.QPixmap(self.tile_res, self.tile_res).fill()

        self.path = 'tile.openstreetmap.org'
        self.path_pre = ['a', 'b', 'c']
    
        self.disk_cache = QtNetwork.QNetworkDiskCache(self)
        self.disk_cache.setCacheDirectory('osm_cache')
        
        self.net_manager = QtNetwork.QNetworkAccessManager(self)
        self.net_manager.setProxy(QtNetwork.QNetworkProxy(
                        QtNetwork.QNetworkProxy.HttpProxy, 'localhost', 3128))
        self.net_manager.setCache(self.disk_cache)
        self.net_manager.finished.connect(self.process_reply)

        self.recalculate_offsets()

    def recalculate_offsets(self):
        ct_x, ct_y = self.coords2tile(self.latitude, self.longitude, self.zoom)
        tx, ty = int(ct_x), int(ct_y)
        # center tile offset
        ctx_offset = math.modf(ct_x)[0] * self.tile_res
        cty_offset = math.modf(ct_y)[0] * self.tile_res
        # center tile top left corner
        cttlx = self.width() / float(2) - ctx_offset
        cttly = self.height() / float(2) - cty_offset
        # window top left tiles delta x and y
        wtltdx = cttlx / self.tile_res
        wtltdy = cttly / self.tile_res
        # top left tile offset in pixels
        self.x_offset = int((1 - math.modf(wtltdx)[0]) * self.tile_res)
        self.y_offset = int((1 - math.modf(wtltdy)[0]) * self.tile_res)

        max_tiles_x = int(math.ceil(self.width()/float(self.tile_res))) + 1
        max_tiles_y = int(math.ceil(self.height()/float(self.tile_res))) + 1
        leftmost = tx - int(math.ceil(wtltdx))
        topmost = ty - int(math.ceil(wtltdy))
        self.visible_rect = QtCore.QRect(leftmost, topmost,
                                   max_tiles_x, max_tiles_y)
        self.download()
        self.update()

    def tiles_to_load(self):
        for x in xrange(self.visible_rect.width()):
            for y in xrange(self.visible_rect.height()):
                tx = x + self.visible_rect.left()
                ty = y + self.visible_rect.top()
                px = x * self.tile_res - self.x_offset
                py = y * self.tile_res - self.y_offset
                yield (tx, ty, self.zoom, px, py)

    def render(self, p, rect):
        for tile, pixmap in self.tiles.iteritems():
            tile_rect = QtCore.QRect(tile[3], tile[4],
                                     self.tile_res, self.tile_res)
            if rect.intersects(tile_rect):
                p.drawPixmap(tile_rect, pixmap)
                #p.drawRect(tile_rect)
        p.drawLine(0, self.height() / 2, self.width(), self.height() / 2)
        p.drawLine(self.width() / 2, 0, self.width() / 2, self.height())
    
    def slip(self, delta):
        ct_x, ct_y = self.coords2tile(self.latitude, self.longitude, self.zoom)
        ct_x += delta[0] / self.tile_res
        ct_y += delta[1] / self.tile_res
        self.latitude, self.longitude = self.tile2coords(ct_x, ct_y, self.zoom)
        self.recalculate_offsets()
        
    def mag(self, delta):
        if self.zoom >= self.max_zoom and delta > 0\
            or (self.zoom <= self.min_zoom) and delta <0:
            return
        self.zoom += delta
        self.recalculate_offsets()

    def generate_url(self):
        while True:
            for i in xrange(len(self.path_pre)):
                yield 'http://' + self.path_pre[i] + '.'\
                      + self.path + '/%d/%d/%d.png'

    def download(self):
        self.tiles.clear()
        for tile in self.tiles_to_load():
            tile_url = self.generate_url().next() % (self.zoom, tile[0], tile[1])
            tile_request = QtNetwork.QNetworkRequest(QtCore.QUrl(tile_url))
            tile_request.setAttribute(QtNetwork.QNetworkRequest.User,
                                      list(tile))
            tile_request.setRawHeader('User-Agent', 'Map-O-Rama (PyQt) 1.0')
            self.net_manager.get(tile_request)
    
    def process_reply(self, reply):
        img = QtGui.QImage()
        qv = reply.request().attribute(QtNetwork.QNetworkRequest.User)
        ls = []
        for num in qv.toList():
            val, not_err = num.toInt()
            if not_err:
                ls.append(val)
            else:
                print "QVariant.toInt() Error"
        tile = tuple(ls)
        if not reply.error():
            if img.load(reply, None):
                self.tiles[tile] = QtGui.QPixmap.fromImage(img)
        else:
            print reply.error()
        reply.deleteLater()
        self.update(QtCore.QRect(tile[3], tile[4],
                                 self.tile_res, self.tile_res))

    def coords2tile(self, lat, lon, zoom):
        maxtile = 1 << zoom
        tx = float((lon + 180) / 360 * maxtile)
        ty = maxtile * ((1 - (math.log(math.tan(math.radians(lat)) +
                                1 / math.cos(math.radians(lat))))/math.pi)/2)
        return (tx, ty)

    def tile2coords(self, tx, ty, zoom):
        maxtile = 1 << zoom
        lon = tx / maxtile * 360.0 - 180.0
        lat = math.atan(math.sinh(math.pi * (1 - 2 * ty / maxtile)))\
              * 180 / math.pi 
        return (lat, lon)

    def paintEvent(self, event): 
        p = QtGui.QPainter()
        p.begin(self)
        self.render(p, event.rect())
        p.drawText(self.rect(), QtCore.Qt.AlignBottom | QtCore.Qt.TextWordWrap,
                   'lat: %f   lon:%f  zoom:%d' %
                   (self.latitude, self.longitude, self.zoom))
        p.end()
    
    def resizeEvent(self, event):
        self.recalculate_offsets()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Up:
            self.slip((0, -20.0,))
        elif event.key() == QtCore.Qt.Key_Down:
            self.slip((0, 20.0,))
        elif event.key() == QtCore.Qt.Key_Left:
            self.slip((-20.0, 0,))
        elif event.key() == QtCore.Qt.Key_Right:
            self.slip((20.0, 0,))
        elif event.key() == QtCore.Qt.Key_Plus:
            self.mag(1)
        elif event.key() == QtCore.Qt.Key_Minus:
            self.mag(-1)


class MapWindow(QtGui.QMainWindow):

    def __init__(self):
        super(MapWindow, self).__init__(None)
        self.resize(256*4, 256*3)
        self.osmmap = OSMMap(self.width(), self.height(), self)
        self.setCentralWidget(self.osmmap)
        self.osmmap.setFocus()
        self.osmmap.show()


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    w = MapWindow()
    w.setWindowTitle('Map-O-Rama')
    w.show()
    sys.exit(app.exec_())
