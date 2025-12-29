# Urch/commands/sort.py
import io
import random

import discord
import matplotlib.pyplot as plt
from discord import app_commands
from discord.ext import commands
from PIL import Image


class SortCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sort", description="Visualize a sorting algorithm")
    @app_commands.describe(
        size="Size of the array to be sorted",
        algorithm="Sorting algorithm to use"
    )
    @app_commands.choices(algorithm=[
        app_commands.Choice(name="Bubble", value="bubble"),
        app_commands.Choice(name="Selection", value="selection"),
        app_commands.Choice(name="Insertion", value="insertion"),
        app_commands.Choice(name="Merge", value="merge"),
        app_commands.Choice(name="Quick", value="quick"),
        app_commands.Choice(name="Heap", value="heap"),
        app_commands.Choice(name="Cocktail", value="cocktail"),
        app_commands.Choice(name="Gnome", value="gnome"),
        app_commands.Choice(name="Shell", value="shell"),
    ])
    async def sort(self, interaction: discord.Interaction, 
                   size: int, 
                   algorithm: str = "bubble"):
        
        if size < 2 or size > 25:
            await interaction.response.send_message("Size must be between 2 and 25.", ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)
        array = [random.randint(1, 100) for _ in range(size)]
        
        # Dictionary mapping algorithm names to their visualization functions
        sort_functions = {
            "bubble": self.visualize_bubble_sort,
            "selection": self.visualize_selection_sort,
            "insertion": self.visualize_insertion_sort,
            "merge": self.visualize_merge_sort,
            "quick": self.visualize_quick_sort,
            "heap": self.visualize_heap_sort,
            "cocktail": self.visualize_cocktail_sort,
            "gnome": self.visualize_gnome_sort,
            "shell": self.visualize_shell_sort
        }
        
        if algorithm not in sort_functions:
            await interaction.followup.send(f"Unknown algorithm: {algorithm}. Available algorithms: {', '.join(sort_functions.keys())}", ephemeral=True)
            return
        
        # Get the appropriate visualization function and call it
        images = await sort_functions[algorithm](array.copy())

        with io.BytesIO() as image_binary:
            images[0].save(image_binary, format='GIF', append_images=images[1:], save_all=True, duration=500, loop=0)
            image_binary.seek(0)
            await interaction.followup.send(file=discord.File(fp=image_binary, filename=f'{algorithm}_sort.gif'))

    async def visualize_bubble_sort(self, array):
        images = []
        n = len(array)
        for i in range(n):
            for j in range(0, n-i-1):
                if array[j] > array[j+1]:
                    array[j], array[j+1] = array[j+1], array[j]
                images.append(self.create_image(array, "Bubble Sort"))
        return images

    async def visualize_selection_sort(self, array):
        images = []
        n = len(array)
        for i in range(n):
            min_idx = i
            for j in range(i+1, n):
                if array[j] < array[min_idx]:
                    min_idx = j
            array[i], array[min_idx] = array[min_idx], array[i]
            images.append(self.create_image(array, "Selection Sort"))
        return images

    async def visualize_insertion_sort(self, array):
        images = []
        for i in range(1, len(array)):
            key = array[i]
            j = i - 1
            while j >= 0 and array[j] > key:
                array[j + 1] = array[j]
                j -= 1
            array[j + 1] = key
            images.append(self.create_image(array, "Insertion Sort"))
        return images

    async def visualize_merge_sort(self, array):
        images = []
        await self.merge_sort_helper(array, 0, len(array) - 1, images)
        return images

    async def merge_sort_helper(self, array, left, right, images):
        if left < right:
            mid = (left + right) // 2
            await self.merge_sort_helper(array, left, mid, images)
            await self.merge_sort_helper(array, mid + 1, right, images)
            await self.merge(array, left, mid, right, images)

    async def merge(self, array, left, mid, right, images):
        left_arr = array[left:mid+1]
        right_arr = array[mid+1:right+1]

        i = j = 0
        k = left

        while i < len(left_arr) and j < len(right_arr):
            if left_arr[i] <= right_arr[j]:
                array[k] = left_arr[i]
                i += 1
            else:
                array[k] = right_arr[j]
                j += 1
            k += 1
            images.append(self.create_image(array, "Merge Sort"))

        while i < len(left_arr):
            array[k] = left_arr[i]
            i += 1
            k += 1
            images.append(self.create_image(array, "Merge Sort"))

        while j < len(right_arr):
            array[k] = right_arr[j]
            j += 1
            k += 1
            images.append(self.create_image(array, "Merge Sort"))

    async def visualize_quick_sort(self, array):
        images = []
        await self.quick_sort_helper(array, 0, len(array) - 1, images)
        return images

    async def quick_sort_helper(self, array, low, high, images):
        if low < high:
            pi = await self.partition(array, low, high, images)
            await self.quick_sort_helper(array, low, pi - 1, images)
            await self.quick_sort_helper(array, pi + 1, high, images)

    async def partition(self, array, low, high, images):
        pivot = array[high]
        i = low - 1

        for j in range(low, high):
            if array[j] <= pivot:
                i += 1
                array[i], array[j] = array[j], array[i]
                images.append(self.create_image(array, "Quick Sort"))
        
        array[i + 1], array[high] = array[high], array[i + 1]
        images.append(self.create_image(array, "Quick Sort"))
        return i + 1

    async def visualize_heap_sort(self, array):
        images = []
        n = len(array)

        # Build heap
        for i in range(n // 2 - 1, -1, -1):
            await self.heapify(array, n, i, images)

        # Extract elements from heap one by one
        for i in range(n - 1, 0, -1):
            array[0], array[i] = array[i], array[0]
            images.append(self.create_image(array, "Heap Sort"))
            await self.heapify(array, i, 0, images)
        
        return images

    async def heapify(self, array, n, i, images):
        largest = i
        left = 2 * i + 1
        right = 2 * i + 2

        if left < n and array[left] > array[largest]:
            largest = left

        if right < n and array[right] > array[largest]:
            largest = right

        if largest != i:
            array[i], array[largest] = array[largest], array[i]
            images.append(self.create_image(array, "Heap Sort"))
            await self.heapify(array, n, largest, images)

    async def visualize_cocktail_sort(self, array):
        images = []
        n = len(array)
        start = 0
        end = n - 1
        swapped = True

        while swapped:
            swapped = False
            
            # Forward pass
            for i in range(start, end):
                if array[i] > array[i + 1]:
                    array[i], array[i + 1] = array[i + 1], array[i]
                    swapped = True
                    images.append(self.create_image(array, "Cocktail Sort"))
            
            if not swapped:
                break
                
            end -= 1
            swapped = False
            
            # Backward pass
            for i in range(end - 1, start - 1, -1):
                if array[i] > array[i + 1]:
                    array[i], array[i + 1] = array[i + 1], array[i]
                    swapped = True
                    images.append(self.create_image(array, "Cocktail Sort"))
            
            start += 1
        
        return images

    async def visualize_gnome_sort(self, array):
        images = []
        index = 0
        n = len(array)
        
        while index < n:
            if index == 0:
                index += 1
            if array[index] >= array[index - 1]:
                index += 1
            else:
                array[index], array[index - 1] = array[index - 1], array[index]
                images.append(self.create_image(array, "Gnome Sort"))
                index -= 1
        
        return images

    async def visualize_shell_sort(self, array):
        images = []
        n = len(array)
        gap = n // 2

        while gap > 0:
            for i in range(gap, n):
                temp = array[i]
                j = i
                while j >= gap and array[j - gap] > temp:
                    array[j] = array[j - gap]
                    j -= gap
                    images.append(self.create_image(array, "Shell Sort"))
                
                array[j] = temp
                if j != i:  # Only add image if there was an actual change
                    images.append(self.create_image(array, "Shell Sort"))
            gap //= 2
        
        return images

    def create_image(self, array, algorithm_name):
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.bar(range(len(array)), array, color='skyblue', edgecolor='black')
        ax.set_xlabel('Index')
        ax.set_ylabel('Value')
        ax.set_title(f'{algorithm_name} Visualization')
        
        # Add grid for better readability
        ax.grid(axis='y', linestyle='--', alpha=0.7)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)

        image = Image.open(buf)
        return image

async def setup(bot):
    await bot.add_cog(SortCommand(bot))