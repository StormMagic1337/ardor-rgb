from .base import Effect, Param
from .classic import Wave, Plasma, Ripple, Typing, Stars, FireClassic, Breathe, Off
from .storm import Storm
from .rain import Rain
from .fire import Fire
from .music import Equalizer, Pulse
from .ambient import Matrix, Aurora, Liquid

# Order = order in the GUI list and for Ctrl+Alt+Left/Right
ALL = [Storm, Rain, Fire, Equalizer, Pulse, Matrix, Aurora, Liquid,
       Wave, Plasma, Ripple, Typing, Stars, FireClassic, Breathe, Off]
BY_NAME = {cls.name: cls for cls in ALL}
