#!/usr/bin/env python
#-*- coding:utf-8 -*-
import time, datetime
import re
import urllib2
import urllib
from xml.dom.minidom import Document
from lib import stuff
import gtk
from xml.dom.minidom import parseString

import ac_export_settings as settings

class Exporter(object):
    def __init__(self, facts):

        self.facts_in_xml = self.facts_to_xml(facts)

        self.facts_to_send = self._buildResult()

        self.showResultsWindow(self.facts_to_send)

    def facts_to_xml(self, facts):
        "Takes fact list saved in native format and returns facts encoded in xml as Document object"
        doc = Document()
        activity_list = doc.createElement("activities")

        for fact in facts:
            fact.activity= fact.activity.encode('utf-8')
            fact.description = (fact.description or u"").encode('utf-8')
            fact.category = (fact.category or _("Unsorted")).encode('utf-8')
            fact.start_time = fact.start_time.strftime('%Y-%m-%d %H:%M:%S')
            if fact.end_time:
                fact.end_time = fact.end_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                fact.end_time = ""

            fact.tags = ", ".join(fact.tags)
            activity = doc.createElement("activity")
            activity.setAttribute("name", fact.activity)
            activity.setAttribute("start_time", fact.start_time)
            activity.setAttribute("end_time", fact.end_time)
            activity.setAttribute("duration_minutes", str(stuff.duration_minutes(fact.delta)))
            activity.setAttribute("category", fact.category)
            activity.setAttribute("description", fact.description)
            activity.setAttribute("tags", fact.tags)
            activity_list.appendChild(activity)

        return doc.appendChild(activity_list)


    def _fetch_ticket_id(self, proj_id, ticket_id_in_proj):
        req = urllib2.Request(settings.AC_URL+"?path_info=/projects/"+proj_id+
                              "/tickets/"+ticket_id_in_proj+"&token="+settings.API_KEY+
                              '&format=xml')

        try:
            f = urllib2.urlopen(req)
        except:
            return False #TODO NEED POPUP ALERT!
        result = parseString(f.read())
        ticket_id = result.getElementsByTagName('id')[0].childNodes[0].nodeValue
        return ticket_id

    def _buildResult(self):
        activities = self.facts_in_xml.getElementsByTagName("activity")
        result = dict()

        for act in activities:
            project_ticket = re.match(settings.REGEX, act.getAttribute(settings.URL_ATTRIBUTE))
            if not project_ticket:
                continue
            key = project_ticket.string
            value = project_ticket.groupdict()
            ticket_id = self._fetch_ticket_id(value['project'], value['ticket'])
            if not ticket_id:
                continue
            value["ticket_id"] = ticket_id
            value["duration_minutes"] = int(act.getAttribute("duration_minutes"))
            body = act.getAttribute("description").strip()
            if key in result:
                result[key]['duration_minutes'] += value["duration_minutes"]
                if body and body not in result[key]['body']:
                    result[key]['body'].append(body)
            else:
                value["body"] = []
                if body: value["body"].append(body)
                result[key] = value

        return result


    def _postResults(self):
        rez = self.facts_to_send
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")

        for itm in rez.items():
            req = urllib2.Request(settings.AC_URL+"?path_info=/projects/"+itm[1]['project']+"/time/add&token="+settings.API_KEY)
            context = {
                "submitted":"submitted",\
                "time[user_id]": settings.USER_ID,\
                "time[value]": itm[1]['duration_minutes'],\
                "time[record_date]": date,\
                "time[body]": itm[1]['body'],
                "time[parent_id]":itm[1]['ticket_id'],
                "time[billable_status]": 1,
            }

            context = urllib.urlencode(context)
            urllib2.urlopen(req, context)

    def toggleCheck(self, me):
        if not me.get_active():
            self.dont_send_buffer.append(me.get_label())
        else:
            try:
                self.dont_send_buffer.remove(me.get_label())
            except ValueError:
                pass

    def showResultsWindow(self, facts):
        self.dont_send_buffer = [] #do better than this
        all_comments = dict()
        all_times = dict()

        dialog = gtk.Dialog("Tai kaiiii geruma langs...",
                            None,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                             gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

        for item in facts.items():
            comment_entry = gtk.Entry()
            comment_entry.set_text(', '.join(item[1]['body']))
            all_comments[item[0]] = comment_entry

            duration = time.strftime('%H:%M', time.gmtime(int(item[1]['duration_minutes'])*60))
            time_entry = gtk.Entry(5)
            time_entry.set_text(str(duration))
            time_entry.set_width_chars(6)
            all_times[item[0]] = time_entry

            checkbox = gtk.CheckButton(item[0])
            checkbox.set_active(True)
            checkbox.connect("toggled", self.toggleCheck)

            url = gtk.LinkButton(item[0], '(visit)')

            separ = gtk.HSeparator()

            t = gtk.Table(2,3)
            t.attach(checkbox,0,3,0,1)
            t.attach(url, 3,4,0,1)
            t.attach(comment_entry, 0,3,1,2)
            t.attach(time_entry, 3,4,1,2)

            dialog.vbox.pack_start(t)
            dialog.vbox.pack_start(separ)

            t.show()
            url.show()
            comment_entry.show()
            time_entry.show()
            checkbox.show()
            separ.show()

        response = dialog.run()

        if response == gtk.RESPONSE_ACCEPT:
            for key in self.dont_send_buffer:
                del self.facts_to_send[key]

            for key in self.facts_to_send:
                self.facts_to_send[key]['duration_minutes'] = all_times[key].get_text()
                self.facts_to_send[key]['body'] = all_comments[key].get_text()
            self._postResults()

        dialog.destroy()