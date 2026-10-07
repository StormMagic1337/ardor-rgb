from .base import Effect, Param
from .classic import Wave, Plasma, Ripple, Typing, Stars, FireClassic, Breathe, Off
from .storm import Storm
from .rain import Rain
from .fire import Fire
from .music import Equalizer, Pulse
from .ambient import Matrix, Aurora, Liquid
from .remix import (ColorWave, Clouds, Spectrum, Vortex, RainbowRings, Scanner, Arrow, Mosaic, Geometry,
                    RainbowFall, Static)
from .atmos import Snow, Meteors, Fireflies, Surf, Campfire, Glitch, LavaLamp
from .weather_fx import WeatherOutside

# Order = order in the GUI list and for Ctrl+Alt+Left/Right
ALL = [Storm, WeatherOutside, Rain, Snow, Fire, Campfire, Equalizer, Pulse, Meteors, Fireflies, Surf, Matrix, Glitch,
       Aurora, Liquid, LavaLamp,
       ColorWave, Clouds, Spectrum, Vortex, RainbowRings, RainbowFall, Scanner, Arrow, Mosaic, Geometry,
       Wave, Plasma, Ripple, Typing, Stars, FireClassic, Breathe, Static, Off]
BY_NAME = {cls.name: cls for cls in ALL}
