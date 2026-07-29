import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTopics } from "@/hooks/useTopics";

const ALL_TOPICS = "__all__";

interface TopicFilterProps {
  selected: string | null;
  onSelect: (topic: string | null) => void;
}

export function TopicFilter({ selected, onSelect }: TopicFilterProps) {
  const { data: topics } = useTopics();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5 rounded-full">
          {selected ?? "All topics"}
          <ChevronDown className="size-3.5 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuRadioGroup
          value={selected ?? ALL_TOPICS}
          onValueChange={(value) => onSelect(value === ALL_TOPICS ? null : value)}
        >
          <DropdownMenuRadioItem value={ALL_TOPICS}>All topics</DropdownMenuRadioItem>
          {topics?.map((stat) => (
            <DropdownMenuRadioItem key={stat.topic} value={stat.topic}>
              {stat.topic}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
