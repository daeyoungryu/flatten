class Animal:
    def speak(self):
        return "generic"


class Dog(Animal):
    def speak(self):
        return "woof"


class Cat(Animal):
    def speak(self):
        return "meow"


def hacked(self):
    return "HACKED"


Dog.speak = hacked


def main():
    return [animal.speak() for animal in [Dog(), Cat()]]
