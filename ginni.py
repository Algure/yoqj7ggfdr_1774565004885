import sys
import types
from js import document, console, window
from pyodide.ffi import create_proxy
from pyodide.http import pyfetch
import js

import pyodide
import random
import ast
import json

ginni = types.ModuleType('ginni')
idkey = 'savr_nwidid'
import math
import random

import random
import math


class CssFilterSolver:
    def __init__(self, r, g, b, seed=None):
        # target color in 0–1 range
        self.target_r = r / 255.0
        self.target_g = g / 255.0
        self.target_b = b / 255.0
        self.rng = random.Random(seed)

    def solve(self):
        best = self._solve()
        return self._css(best)

    def _solve(self):
        # order:
        # invert, sepia, saturate, hue, brightness, contrast
        mins = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        maxs = [1.0, 1.0, 10.0, 360.0, 3.0, 3.0]

        best_vals = [0, 0, 1, 0, 1, 1]
        best_loss = float("inf")

        # --- Wide random search ---
        for _ in range(800):
            cand = [
                self.rng.uniform(mins[0], maxs[0]),
                self.rng.uniform(mins[1], maxs[1]),
                1 + self.rng.uniform(-1, 1),            # saturate bias
                self.rng.uniform(0, 360),
                1 + self.rng.uniform(-0.5, 0.5),        # brightness
                1 + self.rng.uniform(-0.5, 0.5),        # contrast
            ]

            # clamp properly
            for i in range(6):
                cand[i] = max(mins[i], min(maxs[i], cand[i]))

            loss = self._fitness(cand)
            if loss < best_loss:
                best_loss = loss
                best_vals = cand[:]

        # --- Local refinement (annealing) ---
        cur = best_vals[:]
        cur_loss = best_loss
        iterations = 5000

        for i in range(iterations):
            t = 1 - i / iterations
            scale = 0.4 * t

            cand = cur[:]
            cand[0] += self.rng.uniform(-scale, scale)
            cand[1] += self.rng.uniform(-scale, scale)
            cand[2] += self.rng.uniform(-scale * 5, scale * 5)
            cand[3] += self.rng.uniform(-scale * 120, scale * 120)
            cand[4] += self.rng.uniform(-scale * 1.5, scale * 1.5)
            cand[5] += self.rng.uniform(-scale * 1.5, scale * 1.5)

            for j in range(6):
                cand[j] = max(mins[j], min(maxs[j], cand[j]))

            cand_loss = self._fitness(cand)

            if cand_loss < cur_loss or self.rng.random() < 0.002 + 0.5 * t:
                cur = cand
                cur_loss = cand_loss
                if cur_loss < best_loss:
                    best_loss = cur_loss
                    best_vals = cur[:]

        best_vals[3] = best_vals[3] % 360
        return best_vals

    # -----------------------------

    def _fitness(self, v):
        r, g, b = self._apply_filters(v)
        color_loss = self._color_distance(
            self.target_r, self.target_g, self.target_b,
            r, g, b
        )

        brightness_penalty = max(0, v[4] - 1.6) ** 2 * 6
        contrast_penalty = max(0, v[5] - 1.6) ** 2 * 6
        invert_penalty = (v[0] - 0.5) ** 2 * 2
        saturate_penalty = max(0, v[2] - 3) ** 2 * 0.6
        sepia_penalty = v[1] ** 2 * 0.2

        return (color_loss + brightness_penalty + contrast_penalty +
                invert_penalty + saturate_penalty + sepia_penalty)

    # -----------------------------

    def _apply_filters(self, v):
        r = g = b = 0.0

        # invert
        r = (1 - r) * v[0] + r * (1 - v[0])
        g = (1 - g) * v[0] + g * (1 - v[0])
        b = (1 - b) * v[0] + b * (1 - v[0])

        # sepia
        if v[1] > 0:
            sr, sg, sb = 0.393, 0.769, 0.189
            tr, tg, tb = 0.349, 0.686, 0.168
            ur, ug, ub = 0.272, 0.534, 0.131

            nr = r * sr + g * sg + b * sb
            ng = r * tr + g * tg + b * tb
            nb = r * ur + g * ug + b * ub

            r = self._mix(r, nr, v[1])
            g = self._mix(g, ng, v[1])
            b = self._mix(b, nb, v[1])

        # saturate
        gray = 0.2126 * r + 0.7152 * g + 0.0722 * b
        r = gray + v[2] * (r - gray)
        g = gray + v[2] * (g - gray)
        b = gray + v[2] * (b - gray)

        # hue rotate
        angle = math.radians(v[3])
        cosA = math.cos(angle)
        sinA = math.sin(angle)

        m0 = 0.213 + cosA * 0.787 - sinA * 0.213
        m1 = 0.715 - cosA * 0.715 - sinA * 0.715
        m2 = 0.072 - cosA * 0.072 + sinA * 0.928

        m3 = 0.213 - cosA * 0.213 + sinA * 0.143
        m4 = 0.715 + cosA * 0.285 + sinA * 0.140
        m5 = 0.072 - cosA * 0.072 - sinA * 0.283

        m6 = 0.213 - cosA * 0.213 - sinA * 0.787
        m7 = 0.715 - cosA * 0.715 + sinA * 0.715
        m8 = 0.072 + cosA * 0.928 + sinA * 0.072

        nr = r * m0 + g * m1 + b * m2
        ng = r * m3 + g * m4 + b * m5
        nb = r * m6 + g * m7 + b * m8

        r, g, b = nr, ng, nb

        # brightness
        r *= v[4]
        g *= v[4]
        b *= v[4]

        # contrast
        r = (r - 0.5) * v[5] + 0.5
        g = (g - 0.5) * v[5] + 0.5
        b = (b - 0.5) * v[5] + 0.5

        return (
            max(0, min(1, r)),
            max(0, min(1, g)),
            max(0, min(1, b))
        )

    # -----------------------------

    def _mix(self, a, b, t):
        return a * (1 - t) + b * t

    def _color_distance(self, r1, g1, b1, r2, g2, b2):
        dr = r1 - r2
        dg = g1 - g2
        db = b1 - b2
        return math.sqrt(0.3*dr*dr + 0.59*dg*dg + 0.11*db*db) * 100

    # -----------------------------

    def _css(self, v):
        parts = []

        if v[0] > 0.005:
            parts.append(f"invert({round(v[0]*100)}%)")
        if v[1] > 0.005:
            parts.append(f"sepia({round(v[1]*100)}%)")
        if abs(v[2] - 1) > 0.02:
            parts.append(f"saturate({v[2]:.2f})")
        if abs(v[3]) > 0.5:
            parts.append(f"hue-rotate({round(v[3])}deg)")
        if abs(v[4] - 1) > 0.02:
            parts.append(f"brightness({v[4]:.2f})")
        if abs(v[5] - 1) > 0.02:
            parts.append(f"contrast({v[5]:.2f})")

        return "none" if not parts else " ".join(parts)

def hex_to_rgb(hex_string: str):
    hex_string = hex_string.strip().lstrip("#")

    if len(hex_string) == 3:
        # short hex like #f0a → #ff00aa
        hex_string = "".join(c * 2 for c in hex_string)

    if len(hex_string) != 6:
        raise ValueError("Invalid hex color")

    r = int(hex_string[0:2], 16)
    g = int(hex_string[2:4], 16)
    b = int(hex_string[4:6], 16)

    return r, g, b
    

def hex_to_css_filter(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    solver = CssFilterSolver(r, g, b, seed=42)
    css_filter = solver.solve()
    return css_filter
    

class GinNode:
    def __init__(self, id):
        """Setup reference to widget. id must be a string which is the exact name of the widget in the json"""
        self.id = id

    def _get_doc(self):
        doc = document
        if type(self.id) == list:
            for i in self.id:
                if (type(i) == tuple):
                    iframe = doc.getElementById(i[1])
                    doc = iframe
                else:
                    return doc.querySelector('.' + i)
            return doc
        elif type(self.id) == tuple:
            iframe = doc.getElementById(self.id[1])
            doc = iframe
            return doc
        else:
            return doc.querySelector('.' + self.id)

    def set_text_context(self, text_content):
        """Set the text content of a TEXT widget"""
        self._get_doc().textContent = text_content

    def get_text_context(self) -> str:
        """Return the text content of a TEXT widget"""
        return str(self._get_doc().textContent)

    def set_value(self, value):
        """Set the HTML content value of a widget"""
        if self._get_doc().tagName == 'INPUT' or self._get_doc().tagName == 'TEXTAREA':
            self._get_doc().value = value
            return 
        self._get_doc().textContent = value
        
    def get_value(self) -> str:
        """Get the HTML content value of a widget"""
        if self._get_doc().tagName == 'INPUT' or self._get_doc().tagName == 'TEXTAREA':
            return str(self._get_doc().value)
        return str(self._get_doc().textContent)

    def get_img_src(self) -> str:
        """Get the image URL of a TEXT widget"""
        return str(self._get_doc().src)

    def set_img_src(self, src):
        """Set the image URL of an IMAGE widget"""
        element = self._get_doc()
        if 'img' in str(element.tagName).lower():
            element.src = src
        else:
            element.style.backgroundImage = f"url('{str(src).strip()}')"

    def set_background_img(self, src):
        """Set the background image of an IMAGE widget"""
        self._get_doc().style.backgroundImage = f"url('{src}')"

    def set_position_type(self, position):
        """Set the HTML position type of a widget. It could be 'relative', 'absolute' etc."""
        self._get_doc().style.position = position

    def get_background_img(self) -> str:
        """Set the background image of a widget"""
        doc = self._get_doc()
        style = window.getComputedStyle(doc, False)
        return str(style.backgroundImage)[5:-2]

    def set_on_click(self, onclick_function):
        """Set the on click function property of a widget. onclick_function must have 1 event parameter.
        example:
        import ginni as g

        btn = g.GinNode('btn')
        txt = g.GinNode('txt')

        def btn_click_action(event):
            txt.set_text_context('btn clicked')

        btn.set_on_click(btn_click_action)
        """
        self.proxy_f = create_proxy(onclick_function)
        self._get_doc().addEventListener('click', self.proxy_f)
        setClickAnim(self._get_doc())
        
    def set_on_input(self, oninput_function):
        """Set the on input property of a text widget. oninput_function must have 1 event parameter.
        example:
        import ginni as g

        btn = g.GinNode('btn')
        txt = g.GinNode('txt')
        
        def oninput_action(event):
            g.print(txt.get_value())

        btn.set_on_input(oninput_action)
        """
        self.proxy_f = create_proxy(oninput_function)
        self._get_doc().addEventListener('input', self.proxy_f)

    def set_border_color(self, color):
        """Set the border color of a widget. Color must be string of hexcode, e.g: #ffaabb"""
        self._get_doc().style.borderColor = color

    def set_color(self, color):
        """Set the background color of a widget. color must be string of hexcode, e.g: #ffaabb"""
        widtype = str(self._get_doc().getAttribute('savrWidType')).lower()
        if widtype == 'text' or widtype=='date':
            self._get_doc().style.color = color
        elif widtype == 'image':
           self._get_doc().style.filter = hex_to_css_filter(color)
        elif widtype == 'stat':
           self._get_doc().style.setProperty('--graph-color', color)
        else:
           self._get_doc().style.backgroundColor = color

    def set_text_color(self, color):
        """Set the text color of a TEXT widget. color must be string of hexcode, e.g: #ffaabb"""
        self._get_doc().style.color = color

    def change_border_width(self, width):
        """Set the border width of a widget. width must be string that includes the unit e.g '5px' """
        self._get_doc().style.borderWidth = width


    def set_visibility(self, is_visible):
        """Set the visibility of a widget. is_visible must be a boolean of value True or False """
        if is_visible:
            visibility = 'block'
        else:
            visibility = 'none'
        set_savr_visibility(self._get_doc(), visibility)

    def set_width(self, width):
        """Set the width of a widget. width must be string that includes the unit e.g '150px' """
        self._get_doc().style.width = width

    def set_height(self, height):
        """Set the height of a widget. width must be string that includes the unit e.g '150px' """
        self._get_doc().style.height = height

    def get_width(self):
        """Get the runtime width of a widget. width will include the unit e.g '150px' """
        return self._get_doc().style.width

    def get_height(self):
        """Get the runtime height of a widget. width will include the unit e.g '150px' """
        return self._get_doc().style.height


    def set_left(self, left):
        """Set the position of the widget from the left of the screen. left must include the unit e.g '150px' """
        self._get_doc().style.left = left
        self._get_doc().style.position = 'absolute'


    def set_right(self, right):
        """Set the position of the widget from the right of the screen. right must include the unit e.g '150px' """
        self._get_doc().style.right = right
        self._get_doc().style.position = 'absolute'


    def set_top(self, top):
        """Set the position of the widget from the top of the screen. top must include the unit e.g '150px' """
        self._get_doc().style.top = top
        self._get_doc().style.position = 'absolute'


    def set_bottom(self, bottom):
        """Set the position of the widget from the bottom of the screen. bottom must include the unit e.g '150px' """
        self._get_doc().style.bottom = bottom
        self._get_doc().style.position = 'absolute'


    def justify(self, value):
        """Justify content"""
        justifySavr(self._get_doc(), value)


    def set_marginLeft(self, marginLeft):
        """Set the margin of the widget from the left of the parent widget. marginLeft must include the unit e.g '150px' """
        self._get_doc().style.marginLeft = marginLeft

    def set_marginTop(self, marginTop):
        """Set the margin of the widget from the top of the parent widget. marginTop must include the unit e.g '150px' """
        self._get_doc().style.marginTop = marginTop

    def set_marginRight(self, marginRight):
        """Set the margin of the widget from the right of the parent widget. marginRight must include the unit e.g '150px' """
        self._get_doc().style.marginRight = marginRight

    def set_marginBottom(self, marginBottom):
        """Set the margin of the widget from the bottom of the parent widget. marginBottom must include the unit e.g '150px' """
        self._get_doc().style.marginBottom = marginBottom

    def remove(self):
        """Destroy widget permanently and remove from screen"""
        self._get_doc().remove()


    def scroll_to_me(self):
        """Scroll screen to point"""
        self._get_doc().scrollIntoView()


    def play_recording(self, url):
        """
        Play the MP3 recording URL
        :param url: MP3 URL
        :return: null.
        """
        playRecording(self._get_doc(), url)


    def set_stream(self, link):
        """Destroy widget permanently and remove freom screen"""
        self._get_doc().innerHTML = f"""<video width="100%" height="100%" controls autoplay>
        <source src="{link}">
        Your browser does not support the video tag.
      </video>"""


    def get_id(self):
        if type(self.id) == list:
            nid = [i for i in self.id if type(i) == tuple]
            return nid
        elif type(self.id) == tuple:
            nid = [self.id]
            return nid
        given_id = self.id
        try:
            idlist = get(idkey + '_' + given_id)
            return ast.literal_eval(idlist)
        except:
            pass


    def get_parent_id(self):
        if type(self.id) == list:
            nid = [i for i in self.id if type(i) == tuple]
            return nid
        elif type(self.id) == tuple:
            nid = [self.id]
            return nid
        return None


    def render_chart(self, dataMap, chartType, chartName):
        """Set the data for a CHART widget.
        dataMap: Dictionary of x,y values of the data to be displayed
        example:
        stat = g.GinNode('stat')
        dataMap = { 'Red': 12, 'Blue': 19, 'Yellow': 3, 'Green': 5 };
        stat.render_chart(dataMap, 'pie', chartName='Dataset')
        """
        render2DChart(f"{dataMap}", chartType, self.id, chartName)


    def set_dropdown_element(self, content):
        """
        Set a dropdown element with text content
        :param content: text name of content.
        :return:
        """
        randid = 'eldrop'+generate_random_string(10)
        setDropdownElement(content, self._get_doc(), randid)
        return GinNode(randid)


    def get_child(self, name):
        """ Get a GinNode reference to the child widget contained within a widget.
        USed especially when a widget is created at runtime"""

        selid = '.' + name.replace(' ', '_')
        childElements = self._get_doc().getElementsByTagName('*')

        if len(childElements) == 0:
            return None
        else:
            nid = name
            if type(self.id) == list:
                nid = [i for i in self.id if type(i) == tuple]
                nid.append(name)
            elif type(self.id) == tuple:
                nid = [self.id, name]
            return GinNode(nid)


ginni.GinNode = GinNode


class Ginton:
    def __init__(self, text, color, event):
        """Button element for drawup overlay"""
        self.text = text
        self.color = color
        self.event = event
        self.id = generate_random_string(20)
    
    
    def serialize(self):
        return (self.text, self.color, self.id)


ginni.Ginton = Ginton


def generate_random_string(str_size):
    allowed_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(random.choice(allowed_chars) for x in range(str_size))


async def start_recording()-> bool:
    """
    Start recording
    :return: bool.
    """
    return await startRecording()
    
    
async def stop_recording():
    """
    :return: object | null.
    """
    return await stopRecording()
    

def save_item(key, value):
    """
    Save the key/value pair of an item to local storage.
    :param key: The key to be saved to local storage.
    :param value: The value to be saved to local storage.
    :return: null.
    """
    save(key, value)


def remove_item(key):
    """
    Delete a key/value pair from local storage.
    :param key: The key element to be deleted from local storage.
    :return: null
    """
    remove(key)


async def copy_to_clipboard(text) -> bool:
    """
    Copy set text to clipboard.
    :param text: The key element to be deleted from local storage.
    :return: bool
    """
    return await copyToClipboard(text)


async def google_login():
    """
    Login with google
    :return: object of login
    """
    result = type("Obj", (), {})()
    result.uid = get_item('omigoogle_uid')
    result.email = get_item('omigoogle_email')
    print(f' checking in {result.email}')
    if result.email == None or '@' not in result.email:
        await openGoogleLoginAndWait()
    result.uid = get_item('omigoogle_uid')
    result.email = get_item('omigoogle_email')
    result.user_name = get_item('omigoogle_displayName')
    result.photo_url = get_item('omigoogle_photoURL')
    result.id_token = get_item('omigoogle_idToken')
    remove_item('omigoogle_uid')
    remove_item('omigoogle_email')
    remove_item('omigoogle_displayName')
    remove_item('omigoogle_photoURL')
    remove_item('omigoogle_idToken')
    print(f' logged in {result.email}')
    if '@' not in result.email:
        return None
    return result
    


def get_item(key):
    """
    Get the value of a key from local storage.
    :param key: The key element to be gotten from local storage.
    :return: null
    """
    return get(key)


async def create_widget_type(template_id, parent_id):
    """
    Creates a new widget that is a replica of the widget of name template_id make
    replicated widget the child of the screen widget of name parent_id.
    The children of the widget of name template_id will be created along with it
    :param template_id: name of widget on canvas to be duplicated or recreated
    :param parent_id: name of parent widget, which created widget will be a child of.
    :return: a GinNode reference to the newly created widget. New widget is a container to the created widget
     and all components of the new widget must be fetched with the GinNode.get_child(widget_name) function
    """
    iframe_template = get(template_id)
    if iframe_template is None or '<' not in iframe_template:
        iframe_template = await getHtmlFileContent(template_id)
    randid = generate_random_string(10)
    create_element(iframe_template, parent_id, randid)
    parent_id = GinNode(parent_id).get_id()
    nid = ('iframe', randid)
    if parent_id != None:
        nid = parent_id.append(nid)
    return GinNode(nid)


def show_overlay():
    """
    Prints log to debugger console
    :param value: Value to be printed to console
    :return: null
    """
    showSavrOverlay()


def close_overlay():
    """
    Prints log to debugger console
    :param value: Value to be printed to console
    :return: null
    """
    closeSavrOverlay()
    

def show_toast(message):
    """
    Prints log to debugger console
    :param value: Value to be printed to console
    :return: null
    """
    show_savr_toast(message)


def print(value):
    """
    Prints log to debugger console
    :param value: Value to be printed to console
    :return: null
    """
    consolelog(f"{value}")


def printre(value):
    """
    Prints error log to console.
    :param value: Value to be printed as error to console.
    :return: null
    """
    consolelogerror(f"{value}")


def moveto(value):
    """
    Navigate to a different screen at runtime. e.g g.moveto("Screen2")
    :param value: Name of screen
    :return: null
    """
    movetopage(f"{value}")
    

async def upload_file(fileUrl, uploadEndpoint, customHeaders = {})-> bool:
    """
    upload media from local machine. e.g g.upload_file()
    :param fileUrl:  local URL of file
    :param uploadEndpoint: public URL of file upload endpoint
    :param customHeaders: Map of request headers
    :return bool: If task was a success or not.
    """
    return await upload_savr_file(fileUrl, uploadEndpoint, json.dumps(customHeaders)) 
    
    
async def select_media(type:str='image/*,video/*,audio/*'):
    """
    Select media from local machine. e.g g.select_media()
    :param value: none
    :return: String
    """
    if not type.endswith('/*'):
        type += '/*'
    return await get_file(type)
    
    
def open_link(link):
    """
    Open any type of link. e.g g.openlink(link)
    :param value: none
    :return: None
    """
    opensavrlink(link)
    
    
def open_drawup(image=None, title=None, details=None, buttons=[], back_color= '#f8f9fa', text_color= '#333', onimg_click=None):
    """
    Open drawup with the given details. e.g g.open_drawup(image:'https://via.placeholder.com/500x500/4CAF50/FFFFFF?text=Demo+Image')
    :param value: none
    :return: None
    """
    res = []
    for btn in buttons:
        if type(btn) == Ginton:
            res.append(btn.serialize())
    openOverlay(
        json.dumps({'imageURL': str(image) if image is not None else None, 
        'titleText': str(title) if title is not None else None, 
        'detailsText': str(details) if details is not None else None,
        'buttonsList': res,
        'backgroundColor': str(back_color) if back_color is not None else None,
        'textColor': str(text_color) if text_color is not None else None})
    )
    def main_clicked(event):
        if onimg_click is not None:
            img = onimg_click()
            document.getElementById('drawupOverlayPanelImage_Element').src  = img
    if onimg_click is not None:
        proxy_f = create_proxy(main_clicked)
        document.getElementById('drawupOverlayPanelImage_Element').addEventListener('click', proxy_f)
    
    for btn in buttons:
        if type(btn) == Ginton:
            proxy_f = create_proxy(btn.event)
            document.getElementById(btn.id).addEventListener('click', proxy_f)
    
    
async def make_request(url, header={}, body=None, method='GET'):
    """
    Make a HTTP request to given URL
    :param value: Name of screen
    :return: {'status': statusCode, 'data': data };
    """
    return json.loads(await make_savr_request(url, json.dumps(header), body, method))


ginni.generate_random_string = generate_random_string
ginni.open_drawup = open_drawup
ginni.copy_to_clipboard = copy_to_clipboard
ginni.print = print
ginni.google_login = google_login
ginni.printre = printre
ginni.moveto = moveto
ginni.create_widget_type = create_widget_type
ginni.save_item = save_item
ginni.get_item = get_item
ginni.remove_item = remove_item
ginni.make_request = make_request
ginni.show_overlay = show_overlay
ginni.close_overlay = close_overlay
ginni.show_toast = show_toast
ginni.select_media = select_media
ginni.open_link = open_link
ginni.upload_file = upload_file
ginni.start_recording = start_recording
ginni.stop_recording = stop_recording

# Add module to sys modules
sys.modules['ginni'] = ginni
        