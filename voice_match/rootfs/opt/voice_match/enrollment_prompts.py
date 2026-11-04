"""Reading guidance only; audio acceptance does not check the spoken words."""

PHRASES = (
    "The bright morning sun is shining through the kitchen window while I make breakfast.",
    "Please put the blue shopping bag beside the front door before we leave today.",
    "A little bird landed on the garden fence and sang a cheerful song this morning.",
    "I would like a warm cup of tea and a quiet moment after lunch.",
    "We walked along the winding path and watched the clouds drift over the hills.",
    "Could you remind me to bring my jacket when we go outside this evening?",
    "The fresh bread smells wonderful and there is enough for everyone at the table.",
    "My favourite book is waiting on the shelf next to the small wooden clock.",
    "Tomorrow we might visit the park if the weather stays dry through the afternoon.",
    "Please turn the music down a little so we can hear each other clearly.",
    "There are three red apples and a bunch of yellow bananas in the bowl.",
    "I need to charge my phone before taking the train into town this weekend.",
    "The rain has stopped and tiny drops are sparkling on the leaves outside now.",
    "Let us choose something simple for dinner and write down the ingredients we need.",
    "A friendly dog waited patiently while its owner opened the gate beside the house.",
    "What time does the local shop open on a normal Saturday morning in winter?",
    "I found a green scarf tucked behind the cushions on the comfortable living room sofa.",
    "We should check the calendar before arranging another visit with our friends next week.",
    "The silver moon appeared above the rooftops as the street lights began to glow.",
    "Please leave a little space between the boxes so the cupboard door closes properly.",
    "After a busy day I enjoy listening to a story while the kettle boils.",
    "How many people are coming for lunch and will we need another chair today?",
    "The children drew colourful pictures of mountains and rivers using pencils from the drawer.",
    "I will water the plants near the window after opening the curtains this morning.",
    "Our journey took us past an old stone bridge and through a peaceful village.",
    "Could you tell me whether the temperature will drop before we return home tonight?",
    "There is a small parcel waiting by the stairs with a handwritten note attached.",
    "We heard gentle waves along the shore and watched the boats return to harbour.",
    "Please help me remember where I left the spare keys after yesterday's shopping trip.",
    "When the washing is finished I will hang the clean towels outside to dry.",
)


def prompt_for_sample(count, target):
    """Select by saved count, including resumed sessions and legacy 1–100 targets."""
    if type(count) is not int or count < 0 or type(target) is not int or not 1 <= target <= 100:
        raise ValueError("Expected a nonnegative saved count and a sample target from 1 to 100")
    return PHRASES[count % len(PHRASES)] if count < target else None
