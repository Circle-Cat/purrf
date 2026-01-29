import { useMemo } from "react";
import { Check, ChevronDown, X, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import {
  Command,
  CommandList,
  CommandItem,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandSeparator,
} from "@/components/ui/command";
import { cn } from "@/lib/utils";

export default function MultipleSelector({
  options = [],
  value = [],
  onChange,
  placeholder = "Select options...",
  disabled = false,
  showSelectAll = false,
  groupBy = "",
  maxSelected = Number.MAX_SAFE_INTEGER,
  onMaxSelected,
  className,
}) {
  // 分组逻辑
  const groupedOptions = useMemo(() => {
    if (!groupBy) {
      return { __FLAT__: options };
    }
    return options.reduce((acc, obj) => {
      const key = obj[groupBy] || "Others";
      if (!acc[key]) acc[key] = [];
      acc[key].push(obj);
      return acc;
    }, {});
  }, [options, groupBy]);

  // 基础逻辑：判定是否已全选
  const isAllSelected =
    options.length > 0 &&
    options.every((o) => value.some((v) => v.id === o.id));

  // 核心逻辑：判定在当前 maxSelected 限制下，是否允许“全选”操作
  const canSelectAll = maxSelected >= options.length;

  // 切换单个选项
  const toggleValue = (option) => {
    if (disabled) return;
    const isSelected = value.some((v) => v.id === option.id);

    if (!isSelected && value.length >= maxSelected) {
      onMaxSelected?.(maxSelected);
      return;
    }

    onChange(
      isSelected ? value.filter((v) => v.id !== option.id) : [...value, option],
    );
  };

  // 切换分组
  const toggleGroup = (groupOptions) => {
    if (disabled) return;
    const groupIds = groupOptions.map((o) => o.id);
    const selectedInGroup = value.filter((v) => groupIds.includes(v.id));

    // 如果该组已全选，则取消全选该组
    if (selectedInGroup.length === groupOptions.length) {
      onChange(value.filter((v) => !groupIds.includes(v.id)));
      return;
    }

    // 计算新增项
    const newItems = groupOptions.filter(
      (o) => !value.some((v) => v.id === o.id),
    );

    // 检查限制
    if (value.length + newItems.length > maxSelected) {
      onMaxSelected?.(maxSelected);
      return;
    }

    const otherGroupsSelected = value.filter((v) => !groupIds.includes(v.id));
    onChange([...otherGroupsSelected, ...groupOptions]);
  };

  // 处理全局全选
  const handleSelectAll = () => {
    if (!canSelectAll) {
      onMaxSelected?.(maxSelected);
      return;
    }
    onChange([...options]);
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          disabled={disabled}
          aria-label="select-trigger"
          className={cn(
            "flex p-1 rounded-md border min-h-10 h-auto items-center justify-between bg-inherit hover:bg-inherit",
            className,
          )}
        >
          <div className="flex flex-wrap gap-1 items-center px-2">
            {value.length === 0 && (
              <span className="text-sm text-muted-foreground">
                {placeholder}
              </span>
            )}

            {value.map((item) => (
              <Badge
                key={item.id}
                variant="secondary"
                className="flex items-center gap-1 my-0.5"
              >
                <span className="max-w-[120px] truncate">{item.name}</span>
                {!disabled && (
                  <div
                    role="button"
                    aria-label={`Remove ${item.name}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleValue(item);
                    }}
                    className="ml-1 h-4 w-4 cursor-pointer hover:bg-black/10 rounded-full flex items-center justify-center transition-colors"
                  >
                    <XCircle className="h-3 w-3 text-muted-foreground/80" />
                  </div>
                )}
              </Badge>
            ))}
          </div>

          <div className="flex items-center gap-1 shrink-0 px-2">
            {/* 数量进度展示 */}
            {maxSelected !== Number.MAX_SAFE_INTEGER && (
              <span className="text-[10px] text-muted-foreground tabular-nums mr-1">
                {value.length}/{maxSelected}
              </span>
            )}

            {/* 一键清空 */}
            {value.length > 0 && !disabled && (
              <>
                <div
                  role="button"
                  aria-label="Clear all selections"
                  onClick={(e) => {
                    e.stopPropagation();
                    onChange([]);
                  }}
                  className="flex items-center justify-center h-4 w-4 cursor-pointer text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="h-4 w-4" />
                </div>
                <Separator orientation="vertical" className="flex h-4 mx-1" />
              </>
            )}

            <ChevronDown className="h-4 w-4 opacity-50 text-muted-foreground" />
          </div>
        </Button>
      </PopoverTrigger>

      <PopoverContent
        className="p-0 w-[var(--radix-popover-trigger-width)]"
        align="start"
        onWheel={(e) => e.stopPropagation()}
      >
        <Command className="flex flex-col h-full">
          <CommandInput placeholder="Search..." />
          <CommandList className="max-h-[300px] overflow-y-auto overflow-x-hidden">
            <CommandEmpty>No results found.</CommandEmpty>

            {Object.entries(groupedOptions).map(([groupName, items]) => {
              const isFlatMode = groupName === "__FLAT__";
              const isAllGroupSelected =
                items.length > 0 &&
                items.every((item) => value.some((v) => v.id === item.id));

              return (
                <CommandGroup
                  key={groupName}
                  heading={
                    !isFlatMode ? (
                      <div className="flex items-center justify-between w-full group/header">
                        <span>{groupName}</span>
                        {!disabled && (
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              toggleGroup(items);
                            }}
                            className="text-[10px] uppercase font-bold text-primary opacity-0 group-hover/header:opacity-100 transition-opacity"
                          >
                            {isAllGroupSelected
                              ? "Deselect Group"
                              : "Select Group"}
                          </button>
                        )}
                      </div>
                    ) : undefined
                  }
                >
                  {items.map((option) => {
                    const isSelected = value.some((v) => v.id === option.id);
                    const isReachedLimit =
                      !isSelected && value.length >= maxSelected;

                    return (
                      <CommandItem
                        key={option.id}
                        onSelect={() => toggleValue(option)}
                        className={cn(
                          "cursor-pointer",
                          isReachedLimit && "opacity-30 cursor-not-allowed",
                        )}
                      >
                        <div
                          className={cn(
                            "mr-2 flex h-4 w-4 items-center justify-center rounded-sm border border-primary",
                            isSelected
                              ? "bg-primary text-primary-foreground"
                              : "opacity-50",
                          )}
                        >
                          {isSelected && <Check className="h-4 w-4" />}
                        </div>
                        <span className="truncate">{option.name}</span>
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              );
            })}

            {/* 全选按钮区域 */}
            {showSelectAll && options.length > 0 && (
              <>
                {/* 
                  逻辑：
                  1. 如果已经全选了，显示 Deselect All (允许用户清空)
                  2. 如果没全选，且最大限制允许全选所有项，显示 Select All
                  3. 如果 maxSelected < options.length，不显示 Select All 入口
                */}
                {(isAllSelected || canSelectAll) && (
                  <>
                    <CommandSeparator />
                    <div className="p-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full text-xs h-8"
                        onClick={() => {
                          if (isAllSelected) {
                            onChange([]);
                          } else {
                            handleSelectAll();
                          }
                        }}
                      >
                        {isAllSelected ? "Deselect All" : "Select All"}
                      </Button>
                    </div>
                  </>
                )}
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
