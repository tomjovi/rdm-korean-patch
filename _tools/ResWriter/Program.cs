using System.Text.Json;
using System.Resources;

// Args: <input.json> <output.resources>
if (args.Length < 2)
{
    Console.Error.WriteLine("Usage: ResWriter <input.json> <output.resources>");
    return 1;
}

var map = JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(args[0]))
          ?? new Dictionary<string, string>();

using var rw = new ResourceWriter(args[1]);
foreach (var (k, v) in map)
    rw.AddResource(k, v ?? "");
rw.Generate();
Console.WriteLine($"Wrote {args[1]} ({new FileInfo(args[1]).Length} bytes, {map.Count} entries)");
return 0;
