local function gamble()
    print("rolled")
    print("dopamine")
    return "yummers"
end)

if update:GetAttribute("NewUpdate") == true then
   print(gamble())
end
