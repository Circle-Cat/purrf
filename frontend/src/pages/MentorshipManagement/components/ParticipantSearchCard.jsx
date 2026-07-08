import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ParticipantSearchTab from "@/pages/MentorshipManagement/components/ParticipantSearchTab";

/**
 * Displays participant search in separate Participant and Non-participant tabs.
 *
 * @param {{
 *   rounds: Array<{ id: number, name: string }>
 * }} props
 *   Used for the Round filter dropdown in participant search.
 */
const ParticipantSearchCard = ({ rounds = [] }) => {
  return (
    <Card className="mt-6 border-gray-200">
      <CardHeader>
        <CardTitle>Participant Search</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="participant">
          <TabsList className="mb-4 gap-1">
            <TabsTrigger
              value="participant"
              className="px-4 data-[state=active]:bg-background data-[state=active]:shadow-sm data-[state=active]:font-medium"
            >
              Participants
            </TabsTrigger>
            <TabsTrigger
              value="non_participant"
              className="px-4 data-[state=active]:bg-background data-[state=active]:shadow-sm data-[state=active]:font-medium"
            >
              Non-participants
            </TabsTrigger>
          </TabsList>
          <TabsContent value="participant">
            <ParticipantSearchTab
              participationStatus="participant"
              rounds={rounds}
            />
          </TabsContent>
          <TabsContent value="non_participant">
            <ParticipantSearchTab
              participationStatus="non_participant"
              rounds={rounds}
            />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};

export default ParticipantSearchCard;
