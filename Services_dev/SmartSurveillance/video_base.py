import time
import threading
try:
    from greenlet import getcurrent as get_ident
except ImportError:
    try:
        from thread import get_ident
    except ImportError:
        from _thread import get_ident


'''
    An Event-like class that signals all active clients when a new frame is available.
'''
class VideoEvent(object):
    # Initialize events variable
    def __init__(self):
        self.events = {}

    def wait(self):
        '''Invoked from each client's thread to wait for the next frame.'''
        ident = get_ident()
        if ident not in self.events:
            # this is a new client
            # add an entry for it in the self.events dict
            # each entry has two elements, a threading.Event() and a timestamp
            self.events[ident] = [threading.Event(), time.time()]
        return self.events[ident][0].wait()

    def set(self):
        '''Invoked by the camera thread when a new frame is available.'''
        now = time.time()
        remove = None
        for ident, event in self.events.items():
            if not event[0].isSet():
                # if this client's event is not set, then set it
                # also update the last set timestamp to now
                event[0].set()
                event[1] = now
            else:
                # if the client's event is already set, it means the client
                # did not process a previous frame
                # if the event stays set for more than 5 seconds, then assume
                # the client is gone and remove it
                if now - event[1] > 5:
                    remove = ident
        if remove:
            del self.events[remove]

    def clear(self):
        '''Invoked from each client's thread after a frame was processed.'''
        self.events[get_ident()][0].clear()

'''
    An Base class that signals all active clients when a new frame is available.
'''
class VideoBase(object):
    thread = None  # background thread that reads frames from video stream
    frame = None  # current frame is stored here by background thread
    last_access = 0  # time of last client access to the camera
    event = VideoEvent()
    video_source = 0  # video stream source: camera or video file

    def __init__(self, video_source):
        VideoBase.video_source = video_source
        """Start the background camera thread if it isn't running yet."""
        if VideoBase.thread is None:
            VideoBase.last_access = time.time()

            # start background frame thread
            VideoBase.thread = threading.Thread(target=self._thread)
            VideoBase.thread.start()

            # wait until frames are available
            while self.get_frame() is None:
                time.sleep(0)

    ''' Get current frame from video stream ''' 
    def get_frame(self):
        """Return the current camera frame."""
        VideoBase.last_access = time.time()

        # wait for a signal from the camera thread
        VideoBase.event.wait()
        VideoBase.event.clear()

        return VideoBase.frame

    ''' Abstract interface that implemented by sub-class ''' 
    @staticmethod
    def frames():
        '''Generator that returns frames from the camera.'''
        raise RuntimeError('Must be implemented by subclasses.')

    ''' thread function to process video stream ''' 
    @classmethod
    def _thread(cls):
        '''Launch background thread.'''
        print('Starting videostream thread.')

        frames_iterator = cls.frames()
        for frame in frames_iterator:
            VideoBase.frame = frame
            VideoBase.event.set()  # send signal to clients
            time.sleep(0)

            # if there hasn't been any clients asking for frames in
            # the last 10 seconds then stop the thread
            if time.time() - VideoBase.last_access > 10:
                frames_iterator.close()
                print('Stopping videostream thread due to inactivity.')
                break
        VideoBase.thread = None
