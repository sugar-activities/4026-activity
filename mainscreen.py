# Copyright 2008 by Kate Scheppke and Wade Brainerd.  
# This file is part of Typing Turtle.
#
# Typing Turtle is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Typing Turtle is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Typing Turtle.  If not, see <http://www.gnu.org/licenses/>.

# Import standard Python modules.
import logging, os, math, time, copy, simplejson, locale, datetime, random, re, glob
from gettext import gettext as _

# Import PyGTK.
import gobject, pygtk, gtk, pango

# Import Sugar UI modules.
import sugar.activity.activity
from sugar.graphics import *

# Import activity modules.
import lessonscreen, medalscreen, balloongame
import keyboard

# Temporary SVGs of medals from Wikimedia Commons.
# See the links below for licensing information.
# http://commons.wikimedia.org/wiki/File:Gold_medal_world_centered.svg
# http://commons.wikimedia.org/wiki/File:Silver_medal_world_centered.svg
# http://commons.wikimedia.org/wiki/File:Bronze_medal_world_centered.svg

class TitleScene(gtk.DrawingArea):
    def __init__(self):
        gtk.DrawingArea.__init__(self)

        bundle = sugar.activity.activity.get_bundle_path()
        self.backgroundpixbuf = gtk.gdk.pixbuf_new_from_file(bundle + '/images/main-background.jpg')
        
        self.set_size_request(self.backgroundpixbuf.get_width(), self.backgroundpixbuf.get_height())
        
        self.connect("expose-event", self.expose_cb)
        
        self.title_original = _('Typing Turtle')
        self.title_src = self.title_original
        self.title_text = ''
        self.title_counter = 50
        
        gobject.timeout_add(10, self.timer_cb)

    def expose_cb(self, area, event):
        bounds = self.get_allocation()
        
        gc = self.get_style().fg_gc[gtk.STATE_NORMAL]
        
        self.window.draw_pixbuf(
            gc, self.backgroundpixbuf, 
            event.area.x, event.area.y, 
            event.area.x, event.area.y, event.area.width, event.area.height)
        
        # Animated Typing Turtle title.
        pc = self.create_pango_context()
        
        layout = self.create_pango_layout('')
        layout.set_font_description(pango.FontDescription('Times 45'))
        
        layout.set_text(self.title_original)
        original_size = layout.get_size()
        
        x = (bounds.width-original_size[0]/pango.SCALE)-20
        y = 30

        layout.set_text(self.title_text)        
        self.window.draw_layout(gc, x, y, layout)

    def timer_cb(self):
        self.title_counter -= 1
        if self.title_counter == 0:
            if len(self.title_src) > 0:
                self.title_text += self.title_src[0]
                self.title_src = self.title_src[1:]
                self.queue_draw()
            
            self.title_counter = random.randint(1, 5)
            
        return True
    
class MainScreen(gtk.VBox):
    def __init__(self, activity):
        gtk.VBox.__init__(self)
        
        self.activity = activity
        
        # Build background.
        self.titlescene = TitleScene()
        
        # Build lessons list.
        self.lessonbox = gtk.HBox()
        
        #nexticon = sugar.graphics.icon.Icon(icon_name='go-next')
        #self.nextlessonbtn.add(nexticon)
        nextlabel = gtk.Label()
        nextlabel.set_markup("<span size='8000'>" + _('Next') + "</span>")

        self.nextlessonbtn = gtk.Button()
        self.nextlessonbtn.add(nextlabel)
        self.nextlessonbtn.connect('clicked', self.next_lesson_clicked_cb)
        
        #previcon = sugar.graphics.icon.Icon(icon_name='go-previous')
        #self.prevlessonbtn.add(previcon)
        prevlabel = gtk.Label()
        prevlabel.set_markup("<span size='8000'>" + _('Previous') + "</span>")

        self.prevlessonbtn = gtk.Button()
        self.prevlessonbtn.add(prevlabel)
        self.prevlessonbtn.connect('clicked', self.prev_lesson_clicked_cb)
        
        lessonlabel = gtk.Label()
        lessonlabel.set_markup("<span size='12000'>" + _('Start Lesson') + "</span>")
        
        lessonbtn = gtk.Button()
        lessonbtn.add(lessonlabel)
        lessonbtn.connect('clicked', self.lesson_clicked_cb)
        lessonbtn.modify_bg(gtk.STATE_NORMAL, self.get_colormap().alloc_color('#60b060'))
        
        # Load lessons for this language.
        bundle_path = sugar.activity.activity.get_bundle_path() 
        code = locale.getlocale(locale.LC_ALL)[0]
        path = bundle_path + '/lessons/' + code
        self.load_lessons(path)

        # Fallback to en_US lessons if none found.
        if not len(self.lessons):
            self.load_lessons(bundle_path + '/lessons/en_US')

        # We cannot run without lessons/
        if not len(self.lessons):
            sys.exit(1)

        # Sort by the 'order' field.
        self.lessons.sort(lambda x, y: x.get('order', 0) - y.get('order', 0))

        # Load all the keyboard images.
        self.keyboard_images = keyboard.KeyboardImages()
        self.keyboard_images.load_images()
        
        navbox = gtk.HBox()
        navbox.set_spacing(10)
        navbox.pack_start(self.prevlessonbtn, True)
        navbox.pack_start(lessonbtn, True)
        navbox.pack_start(self.nextlessonbtn, True)
        
        lessonbox = gtk.VBox()
        lessonbox.set_spacing(10)
        lessonbox.pack_start(navbox, False)
        lessonbox.pack_start(self.lessonbox)
        
        self.pack_start(self.titlescene, False, True, 10)
        self.pack_start(lessonbox, True)
        
        self.show_next_lesson()

    def load_lessons(self, path):
        # Find all .lesson files in ./lessons/en_US/ for example.
        self.lessons = []
        for f in glob.iglob(path + '/*.lesson'):
            fd = open(f, 'r')
            try:
                lesson = simplejson.loads(fd.read())
                self.lessons.append(lesson)
            finally:
                fd.close()

    def get_next_lesson(self):
        """Returns the index of the first lesson without a medal."""
        index = len(self.lessons)-1
        for i in xrange(0, len(self.lessons)):
            if self.lessons[i]['order'] >= 0 and \
               not self.activity.data['medals'].has_key(self.lessons[i]['name']):
                index = min(index, i)
        return index
    
    def show_next_lesson(self):
        """Displays the first lesson which the user can activate that does not yet have a medal."""
        self.show_lesson(self.get_next_lesson())
    
    def show_lesson(self, index):
        # Clear all widgets in the lesson box.
        for w in self.lessonbox:
            self.lessonbox.remove(w)
        
        self.prevlessonbtn.set_sensitive(index > 0)
        self.nextlessonbtn.set_sensitive(index < len(self.lessons)-1)
        
        lesson = self.lessons[index]
        
        self.lesson_index = index
        self.visible_lesson = lesson
        
        medal_type = 'none'
        if self.activity.data['medals'].has_key(lesson['name']):
            medal_type = self.activity.data['medals'][lesson['name']]['type']
        
        # Create the lesson button.
        namelabel = gtk.Label()
        namelabel.set_alignment(0.5, 0.5)
        namelabel.set_markup("<span size='20000'><b>" + lesson['name'] + "</b></span>")
        desclabel = gtk.Label()
        desclabel.set_alignment(0.5, 0.5)
        desclabel.set_markup("<span size='10000' color='#808080'>" + lesson['description'] + "</span>")
        
        if medal_type != 'none':
            hint = _('You earned a medal in this lesson!  Advance to the next one\nby clicking the Next button.')
        else:
            hint = ''
                
        #hintlabel = gtk.Label()
        #hintlabel.set_alignment(0.0, 0.8)
        #hintlabel.set_markup("<span size='8000' color='#606020'>" + hint + "</span>")
        
        labelbox = gtk.VBox()
        labelbox.set_spacing(10)
        labelbox.set_border_width(20)
        labelbox.pack_start(namelabel, False)
        labelbox.pack_start(desclabel, False)
        #labelbox.pack_start(hintlabel)

        # Create the medal image.
        bundle = sugar.activity.activity.get_bundle_path()
        images = {
            'none':   bundle+'/images/no-medal.svg',
            'bronze': bundle+'/images/bronze-medal.svg',
            'silver': bundle+'/images/silver-medal.svg',
            'gold':   bundle+'/images/gold-medal.svg'
        }
        medalpixbuf = gtk.gdk.pixbuf_new_from_file(images[medal_type])
        medalpixbuf = medalpixbuf.scale_simple(200, 200, gtk.gdk.INTERP_BILINEAR)
        
        medalimage = gtk.Image()
        medalimage.set_from_pixbuf(medalpixbuf)
        
        names = {
            'none':   _('No Medal Yet'),
            'bronze': _('Bronze Medal'),
            'silver': _('Silver Medal'),
            'gold':   _('Gold Medal'),
        }
        medallabel = gtk.Label(names[medal_type])
        
        medalbox = gtk.VBox()
        medalbox.pack_start(medalimage)
        medalbox.pack_start(medallabel)
        
        medalbtn = gtk.Button()
        medalbtn.add(medalbox)
        medalbtn.connect('clicked', self.medal_clicked_cb)
        
        # Hilite the button in the direction of the first unmedaled lesson.
        next_index = self.get_next_lesson()
        if next_index > self.lesson_index:
            self.nextlessonbtn.modify_bg(gtk.STATE_NORMAL, self.get_colormap().alloc_color('#ff8080'))
        else:
            self.nextlessonbtn.modify_bg(gtk.STATE_NORMAL, self.get_colormap().alloc_color('#40a040'))
        if next_index < self.lesson_index:
            self.prevlessonbtn.modify_bg(gtk.STATE_NORMAL, self.get_colormap().alloc_color('#ff8080'))
        else:
            self.prevlessonbtn.modify_bg(gtk.STATE_NORMAL, self.get_colormap().alloc_color('#40a040'))
        
        self.lessonbox.pack_start(labelbox, True)
        if medal_type != 'none':
            self.lessonbox.pack_start(medalbtn, False)

        self.lessonbox.show_all()
    
    def next_lesson_clicked_cb(self, widget):
        self.show_lesson(self.lesson_index+1)
    
    def prev_lesson_clicked_cb(self, widget):
        self.show_lesson(self.lesson_index-1)
    
    def lesson_clicked_cb(self, widget):
        if self.visible_lesson['type'] == 'balloon':
            reload(balloongame)
            self.activity.push_screen(balloongame.BalloonGame(self.visible_lesson, self.activity))
        else:
            reload(lessonscreen)
            self.activity.push_screen(lessonscreen.LessonScreen(self.visible_lesson, self.keyboard_images, self.activity))
    
    def medal_clicked_cb(self, widget):
        if self.activity.data['medals'].has_key(self.visible_lesson['name']):
            medal = self.activity.data['medals'][self.visible_lesson['name']]
            self.activity.push_screen(medalscreen.MedalScreen(medal, self.activity))
